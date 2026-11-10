"""
Adaptive Confidence Estimator & Policy Action Controller for Text-to-SQL Multi-Agent Orchestration.

Implements multi-signal confidence calculation combining:
1. Model Confidence (C_model)
2. Execution Feedback (C_exec)
3. Verifier Assessment (C_verifier)
4. Candidate Output Agreement (C_agreement)

Together with dynamic policy-based routing implementing the specification:
Action             | Trigger Condition                                       | Priority / Conflict Resolution                               | Purpose
-------------------|---------------------------------------------------------|--------------------------------------------------------------|-----------------------------------
STOP               | Confidence ≥ 0.85, execution successful, verifier ≥ 0.85 | Selected only when all stopping conditions are satisfied     | Return final SQL answer
VERIFY             | Confidence 0.50–0.84, execution successful              | Selected when execution succeeds but confidence is insufficient for STOP | Check semantic correctness
RETRIEVE           | Schema relevance < 0.60                                 | Prioritized when schema mismatch is suspected                | Refine schema context
REPAIR             | Execution error or confidence < 0.50                    | Execution errors take priority over normal confidence-based routing | Correct SQL errors
GENERATE MULTIPLE  | Confidence 0.50–0.70 with ambiguity                     | Selected when multiple plausible SQL interpretations exist   | Generate and compare candidates
GENERATE           | Initial call or after retrieval update                  | Used when no other corrective action is required             | Generate a new SQL candidate
"""

import re
from typing import Dict, List, Any, Optional

# Orchestration Action Definitions
ACTION_STOP = "STOP"
ACTION_VERIFY = "VERIFY"
ACTION_RETRIEVE = "RETRIEVE"
ACTION_REPAIR = "REPAIR"
ACTION_GENERATE_MULTIPLE = "GENERATE MULTIPLE"
ACTION_GENERATE = "GENERATE"

ACTION_POLICY_TABLE = [
    {
        "action": ACTION_STOP,
        "trigger_condition": "Confidence ≥ 0.85, execution successful, verifier ≥ 0.85",
        "priority": "Selected only when all stopping conditions are satisfied",
        "purpose": "Return final SQL answer"
    },
    {
        "action": ACTION_VERIFY,
        "trigger_condition": "Confidence 0.50–0.84, execution successful",
        "priority": "Selected when execution succeeds but confidence is insufficient for STOP",
        "purpose": "Check semantic correctness"
    },
    {
        "action": ACTION_RETRIEVE,
        "trigger_condition": "Schema relevance < 0.60",
        "priority": "Prioritized when schema mismatch is suspected",
        "purpose": "Refine schema context"
    },
    {
        "action": ACTION_REPAIR,
        "trigger_condition": "Execution error or confidence < 0.50",
        "priority": "Execution errors take priority over normal confidence-based routing",
        "purpose": "Correct SQL errors"
    },
    {
        "action": ACTION_GENERATE_MULTIPLE,
        "trigger_condition": "Confidence 0.50–0.70 with ambiguity",
        "priority": "Selected when multiple plausible SQL interpretations exist",
        "purpose": "Generate and compare candidates"
    },
    {
        "action": ACTION_GENERATE,
        "trigger_condition": "Initial call or after retrieval update",
        "priority": "Used when no other corrective action is required",
        "purpose": "Generate a new SQL candidate"
    }
]

ACTION_POLICIES = {entry["action"]: entry for entry in ACTION_POLICY_TABLE}
ACTION_POLICIES["GENERATE_MULTIPLE"] = ACTION_POLICIES[ACTION_GENERATE_MULTIPLE]


class MultiSignalConfidenceEngine:
    """
    Evaluates multi-signal confidence for adaptive handoff and early-exit decisions.
    Formula: C_total = w_model * C_model + w_exec * C_exec + w_verifier * C_verifier + w_agree * C_agree
    """

    def __init__(
        self,
        weight_model: float = 0.25,
        weight_exec: float = 0.35,
        weight_verifier: float = 0.25,
        weight_agreement: float = 0.15,
        base_threshold: float = 0.85
    ):
        # Normalize weights to sum to 1.0
        total_w = weight_model + weight_exec + weight_verifier + weight_agreement
        self.w_model = weight_model / total_w
        self.w_exec = weight_exec / total_w
        self.w_verifier = weight_verifier / total_w
        self.w_agreement = weight_agreement / total_w
        self.base_threshold = base_threshold

    def detect_ambiguity(self, english: str, schema_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Detects whether an English query contains semantic or structural ambiguity:
        - Fuzzy ranking / superlatives without explicit metrics ('best', 'top', 'active')
        - Column names that appear in multiple schema tables without qualification
        - Phrasings that admit multiple plausible SQL interpretations
        """
        text = english.lower().strip()
        reasons = []

        # 1. Fuzzy qualification indicators
        fuzzy_words = [
            'best', 'top', 'active', 'recent', 'popular', 'highest', 'lowest',
            'latest', 'oldest', 'most', 'least', 'good', 'valuable', 'frequent'
        ]
        found_fuzzy = [w for w in fuzzy_words if re.search(r'\b' + re.escape(w) + r'\b', text)]
        if found_fuzzy:
            reasons.append(f"Vague or ambiguous qualifier(s): {', '.join(found_fuzzy)}")

        # 2. Schema-based column ambiguity across tables
        if schema_context and isinstance(schema_context, dict) and len(schema_context) > 1:
            col_counts: Dict[str, List[str]] = {}
            for tbl, cols in schema_context.items():
                col_list = list(cols.keys()) if isinstance(cols, dict) else [str(c) for c in cols]
                for c in col_list:
                    c_clean = str(c).lower()
                    if c_clean not in ['id', 'created_at', 'status']:
                        col_counts.setdefault(c_clean, []).append(tbl)
            for c_name, tbls in col_counts.items():
                if len(tbls) > 1 and re.search(r'\b' + re.escape(c_name) + r'\b', text):
                    reasons.append(f"Ambiguous column '{c_name}' exists in multiple tables ({', '.join(tbls)})")

        # 3. Multiple candidate interpretation patterns
        if ' and ' in text and ' or ' in text:
            reasons.append("Mixed logical operators ('and' + 'or') without clear grouping")

        if any(w in text for w in ['either', 'any of', 'similar to']):
            reasons.append("Disjunctive phrasing with multiple possible WHERE conditions")

        has_ambiguity = len(reasons) > 0
        return {
            "has_ambiguity": has_ambiguity,
            "ambiguity_reasons": reasons
        }

    def calculate_query_complexity(self, english: str, schema_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Assesses natural language query complexity based on:
        - Join depth / entity count
        - Aggregation & grouping functions
        - Nested conditions / subqueries / set operators
        - Temporal / arithmetic operations
        - Ambiguity detection
        """
        text = english.lower().strip()
        signals = []
        score = 0.15  # baseline simple query

        # Join indicators
        join_words = ['join', 'joined', 'together with', 'along with', 'combined', 'across', 'relationship', 'and their']
        has_join = any(w in text for w in join_words)
        if has_join:
            score += 0.25
            signals.append("Multi-table join required")

        # Aggregation indicators
        agg_words = ['count', 'sum', 'total', 'average', 'avg', 'mean', 'maximum', 'max', 'minimum', 'min', 'number of']
        agg_count = sum(1 for w in agg_words if w in text)
        if agg_count > 0:
            score += min(0.20, agg_count * 0.10)
            signals.append(f"Aggregations detected ({agg_count})")

        # Grouping & Sorting indicators
        if 'group by' in text or 'grouped' in text or 'per ' in text or 'for each' in text or 'by category' in text:
            score += 0.15
            signals.append("Grouping clause (GROUP BY / HAVING)")

        if 'order by' in text or 'sorted' in text or 'top ' in text or 'highest' in text or 'lowest' in text or 'recent' in text:
            score += 0.10
            signals.append("Sorting / Ranking / Limit constraint")

        # Complex condition indicators
        condition_count = text.count(' and ') + text.count(' or ') + text.count(' where ') + text.count(' with ')
        if condition_count >= 2:
            score += 0.15
            signals.append(f"Multiple compound conditions ({condition_count})")

        # Subquery / advanced patterns
        if any(w in text for w in ['not in', 'exists', 'greater than average', 'more than average', 'nested', 'second highest']):
            score += 0.25
            signals.append("Subquery / nested relation logic")

        # Ambiguity check
        ambiguity_res = self.detect_ambiguity(english, schema_context)
        if ambiguity_res["has_ambiguity"]:
            score += 0.10
            signals.extend(ambiguity_res["ambiguity_reasons"])

        # Clamp complexity score between 0.1 and 1.0
        complexity_score = round(min(1.0, max(0.1, score)), 2)

        if complexity_score < 0.35:
            category = "SIMPLE"
            dynamic_exit_threshold = 0.85
        elif complexity_score < 0.65:
            category = "MODERATE"
            dynamic_exit_threshold = 0.85
        elif complexity_score < 0.85:
            category = "COMPLEX"
            dynamic_exit_threshold = 0.85
        else:
            category = "EXTRA-HARD"
            dynamic_exit_threshold = 0.85
        # The paper keeps one stop threshold (tau = 0.85) for every question; the difficulty label is for analysis only.
        dynamic_exit_threshold = self.base_threshold

        return {
            "complexity_score": complexity_score,
            "category": category,
            "dynamic_exit_threshold": dynamic_exit_threshold,
            "has_ambiguity": ambiguity_res["has_ambiguity"],
            "ambiguity_reasons": ambiguity_res["ambiguity_reasons"],
            "signals": signals
        }

    def compute_agreement(self, candidate_sql_list: List[str]) -> float:
        """
        Computes consensus / agreement score among candidate SQL outputs.
        Compares ALL generated candidates pairwise rather than only the first two.
        If len == 1, returns a neutral prior (0.50) because no consensus counterpart exists.
        If empty, returns 0.0.
        """
        if not candidate_sql_list:
            return 0.0

        sqls = [re.sub(r'\s+', ' ', s.lower().strip().rstrip(';')) for s in candidate_sql_list if s and s.strip()]
        if not sqls:
            return 0.0

        if len(sqls) == 1:
            # Single candidate has no consensus counterpart to compare; return neutral baseline (0.50)
            return 0.50

        # Exact match across all candidates
        if all(s == sqls[0] for s in sqls):
            return 1.0

        # Compare ALL pairs (i < j)
        pairwise_agreements = []
        clauses = ['select', 'from', 'where', 'join', 'group by', 'order by', 'limit', 'having']

        for i in range(len(sqls)):
            for j in range(i + 1, len(sqls)):
                tokens_a = set(re.findall(r'[a-zA-Z0-9_]+', sqls[i]))
                tokens_b = set(re.findall(r'[a-zA-Z0-9_]+', sqls[j]))

                if not tokens_a and not tokens_b:
                    pairwise_agreements.append(1.0)
                    continue

                intersection = len(tokens_a.intersection(tokens_b))
                union = len(tokens_a.union(tokens_b))
                jaccard = intersection / union if union > 0 else 0.0

                # Structural clause matching
                clause_match = 0
                total_clauses = 0
                for clause in clauses:
                    in_a = clause in sqls[i]
                    in_b = clause in sqls[j]
                    if in_a or in_b:
                        total_clauses += 1
                        if in_a and in_b:
                            clause_match += 1

                struct_sim = (clause_match / total_clauses) if total_clauses > 0 else 1.0
                pair_agree = (jaccard * 0.6) + (struct_sim * 0.4)
                pairwise_agreements.append(pair_agree)

        avg_agreement = sum(pairwise_agreements) / max(1, len(pairwise_agreements))
        return round(min(1.0, max(0.0, avg_agreement)), 3)

    def determine_action(
        self,
        confidence: float,
        execution_success: bool,
        verifier_score: float,
        schema_relevance: float = 1.0,
        has_ambiguity: bool = False,
        has_execution_error: bool = False,
        is_initial: bool = False,
        is_post_retrieval: bool = False,
        threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Determines the precise orchestration action according to the exact policy specification:

        Action             | Trigger Condition                                       | Priority / Conflict Resolution                               | Purpose
        -------------------|---------------------------------------------------------|--------------------------------------------------------------|-----------------------------------
        STOP               | Confidence ≥ 0.85, execution successful, verifier ≥ 0.85 | Selected only when all stopping conditions are satisfied     | Return final SQL answer
        VERIFY             | Confidence 0.50–0.84, execution successful              | Selected when execution succeeds but confidence is insufficient for STOP | Check semantic correctness
        RETRIEVE           | Schema relevance < 0.60                                 | Prioritized when schema mismatch is suspected                | Refine schema context
        REPAIR             | Execution error or confidence < 0.50                    | Execution errors take priority over normal confidence-based routing | Correct SQL errors
        GENERATE MULTIPLE  | Confidence 0.50–0.70 with ambiguity                     | Selected when multiple plausible SQL interpretations exist   | Generate and compare candidates
        GENERATE           | Initial call or after retrieval update                  | Used when no other corrective action is required             | Generate a new SQL candidate
        """
        tau = float(self.base_threshold if threshold is None else threshold)   # stop threshold (paper: tau = 0.85)
        confidence = round(float(confidence), 3)
        verifier_score = round(float(verifier_score), 3)
        schema_relevance = round(float(schema_relevance), 3)

        # 1. Execution errors take priority over normal confidence-based routing, OR confidence < 0.50
        # (Note: confidence < 0.50 applies to generated SQL candidate evaluation; before initial generation, SQL does not exist yet)
        if has_execution_error or (confidence < 0.50 and not is_initial and not is_post_retrieval):
            action = ACTION_REPAIR
            if has_execution_error:
                reason = "Execution error detected. Execution errors take priority over normal confidence-based routing. Correcting SQL errors."
            else:
                reason = f"Confidence ({confidence:.1%}) < 0.50 below viable threshold. Escalating to Repair Agent for targeted correction."

        # 2. Schema relevance < 0.60: Prioritized when schema mismatch is suspected
        elif schema_relevance < 0.60:
            action = ACTION_RETRIEVE
            reason = f"Schema relevance ({schema_relevance:.1%}) < 0.60. Schema mismatch suspected; refining schema context."

        # 3. Confidence 0.50–0.70 with ambiguity: Selected when multiple plausible SQL interpretations exist
        elif (0.50 <= confidence <= 0.70) and has_ambiguity:
            action = ACTION_GENERATE_MULTIPLE
            reason = f"Confidence ({confidence:.1%}) is 0.50–0.70 with detected ambiguity. Multiple plausible interpretations exist; generating and comparing candidates."

        # 4. STOP: Confidence ≥ 0.85, execution successful, verifier ≥ 0.85. Selected only when all stopping conditions are satisfied
        elif confidence >= tau and execution_success and verifier_score >= 0.85:
            action = ACTION_STOP
            reason = f"All stopping conditions satisfied: Confidence ({confidence:.1%}) ≥ {tau:.2f}, execution successful, verifier ({verifier_score:.1%}) ≥ 0.85. Returning final SQL answer."

        # 5. VERIFY: Confidence 0.50–0.84, execution successful. Selected when execution succeeds but confidence is insufficient for STOP
        elif (0.50 <= confidence < tau) and execution_success:
            action = ACTION_VERIFY
            reason = f"Execution succeeded, but confidence ({confidence:.1%}) is below the stop threshold {tau:.2f}. Checking semantic correctness."

        # 6. GENERATE: Initial call or after retrieval update. Used when no other corrective action is required
        elif is_initial or is_post_retrieval:
            action = ACTION_GENERATE
            reason = "Initial invocation or post-retrieval update. No other corrective action required; generating a new SQL candidate."

        else:
            # Fallback when execution failed without error flag or confidence out of normal band
            if not execution_success:
                action = ACTION_REPAIR
                reason = "Execution did not succeed. Escalating to Repair Agent."
            else:
                action = ACTION_VERIFY
                reason = f"Confidence ({confidence:.1%}) insufficient for STOP; checking semantic correctness."

        policy = ACTION_POLICIES[action]
        return {
            "action": action,
            "action_desc": f"[{action}] {reason}",
            "trigger_condition": policy["trigger_condition"],
            "priority": policy["priority"],
            "purpose": policy["purpose"],
            "details": reason,
            "is_terminal": action == ACTION_STOP
        }

    def evaluate_multi_signal(
        self,
        c_model: float,
        c_exec: float,
        c_verifier: float,
        c_agreement: float,
        complexity_info: Dict[str, Any],
        has_error: bool = False,
        schema_relevance: float = 1.0,
        is_initial: bool = False,
        is_post_retrieval: bool = False
    ) -> Dict[str, Any]:
        """
        Computes the final composite multi-signal confidence score and evaluates
        the exact policy action according to the routing table.
        """
        # If execution threw a hard syntax error, execution confidence collapses
        if has_error:
            c_exec = min(c_exec, 0.15)
            c_verifier = min(c_verifier, 0.20)

        # Composite weighted sum
        total_confidence = (
            self.w_model * c_model +
            self.w_exec * c_exec +
            self.w_verifier * c_verifier +
            self.w_agreement * c_agreement
        )
        total_confidence = round(min(1.0, max(0.0, total_confidence)), 3)

        exit_threshold = complexity_info.get("dynamic_exit_threshold", self.base_threshold)
        has_ambiguity = complexity_info.get("has_ambiguity", False)
        execution_success = (c_exec >= 0.70) and not has_error

        # Determine exact orchestration action from policy table
        action_decision = self.determine_action(
            confidence=total_confidence,
            execution_success=execution_success,
            verifier_score=c_verifier,
            schema_relevance=schema_relevance,
            has_ambiguity=has_ambiguity,
            has_execution_error=has_error,
            is_initial=is_initial,
            is_post_retrieval=is_post_retrieval,
            threshold=exit_threshold
        )

        can_early_exit = (action_decision["action"] == ACTION_STOP)

        return {
            "total_confidence": total_confidence,
            "c_model": round(c_model, 3),
            "c_exec": round(c_exec, 3),
            "c_verifier": round(c_verifier, 3),
            "c_agreement": round(c_agreement, 3),
            "schema_relevance": round(schema_relevance, 3),
            "has_ambiguity": has_ambiguity,
            "weights": {
                "w_model": round(self.w_model, 2),
                "w_exec": round(self.w_exec, 2),
                "w_verifier": round(self.w_verifier, 2),
                "w_agreement": round(self.w_agreement, 2)
            },
            "threshold": exit_threshold,
            "can_early_exit": can_early_exit,
            "action": action_decision["action"],
            "action_desc": action_decision["action_desc"],
            "action_trigger": action_decision["trigger_condition"],
            "action_priority": action_decision["priority"],
            "action_purpose": action_decision["purpose"],
            "action_policy_table": ACTION_POLICY_TABLE
        }
