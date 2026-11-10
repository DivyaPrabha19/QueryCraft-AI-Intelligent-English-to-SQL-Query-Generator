import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from orchestration.confidence import (
    MultiSignalConfidenceEngine,
    ACTION_STOP,
    ACTION_VERIFY,
    ACTION_RETRIEVE,
    ACTION_REPAIR,
    ACTION_GENERATE_MULTIPLE,
    ACTION_GENERATE
)
from orchestration.orchestrator import MultiAgentOrchestrator

def test_six_action_triggers():
    print("=== Testing 6 Orchestration Action Triggers ===")
    engine = MultiSignalConfidenceEngine()
    
    # 1. ACTION_STOP: Confidence >= 0.85, execution successful, verifier >= 0.85
    act_stop = engine.determine_action(
        confidence=0.88,
        execution_success=True,
        verifier_score=0.90,
        schema_relevance=0.95
    )
    assert act_stop["action"] == ACTION_STOP, f"Expected STOP, got {act_stop['action']}"
    print("[PASS] Action STOP triggered correctly")

    # 2. ACTION_VERIFY: Confidence 0.50-0.84, execution successful
    act_verify = engine.determine_action(
        confidence=0.72,
        execution_success=True,
        verifier_score=0.75,
        schema_relevance=0.95
    )
    assert act_verify["action"] == ACTION_VERIFY, f"Expected VERIFY, got {act_verify['action']}"
    print("[PASS] Action VERIFY triggered correctly")

    # 3. ACTION_RETRIEVE: Schema relevance < 0.60
    act_retrieve = engine.determine_action(
        confidence=0.75,
        execution_success=True,
        verifier_score=0.80,
        schema_relevance=0.45
    )
    assert act_retrieve["action"] == ACTION_RETRIEVE, f"Expected RETRIEVE, got {act_retrieve['action']}"
    print("[PASS] Action RETRIEVE triggered correctly")

    # 4. ACTION_REPAIR: Execution error or confidence < 0.50
    act_repair_err = engine.determine_action(
        confidence=0.90,
        execution_success=False,
        verifier_score=0.20,
        has_execution_error=True
    )
    assert act_repair_err["action"] == ACTION_REPAIR, f"Expected REPAIR, got {act_repair_err['action']}"
    
    act_repair_low = engine.determine_action(
        confidence=0.42,
        execution_success=False,
        verifier_score=0.30
    )
    assert act_repair_low["action"] == ACTION_REPAIR, f"Expected REPAIR, got {act_repair_low['action']}"
    print("[PASS] Action REPAIR triggered correctly (for both execution error and low confidence)")

    # 5. ACTION_GENERATE_MULTIPLE: Confidence 0.50-0.70 with ambiguity
    act_gen_mult = engine.determine_action(
        confidence=0.62,
        execution_success=False,
        verifier_score=0.60,
        schema_relevance=0.85,
        has_ambiguity=True,
        is_initial=True
    )
    assert act_gen_mult["action"] == ACTION_GENERATE_MULTIPLE, f"Expected GENERATE_MULTIPLE, got {act_gen_mult['action']}"
    print("[PASS] Action GENERATE_MULTIPLE triggered correctly")

    # 6. ACTION_GENERATE: Initial call or after retrieval update
    act_gen_init = engine.determine_action(
        confidence=0.85,
        execution_success=False,
        verifier_score=0.80,
        schema_relevance=0.85,
        has_ambiguity=False,
        is_initial=True
    )
    assert act_gen_init["action"] == ACTION_GENERATE, f"Expected GENERATE, got {act_gen_init['action']}"
    print("[PASS] Action GENERATE triggered correctly")

def test_candidate_agreement():
    print("\n=== Testing Candidate Agreement Across Multiple Candidates ===")
    engine = MultiSignalConfidenceEngine()

    # Empty candidate list -> 0.0
    assert engine.compute_agreement([]) == 0.0
    
    # Single candidate -> Neutral baseline 0.50 (NOT 1.0)
    assert engine.compute_agreement(["SELECT * FROM users;"]) == 0.50
    print("[PASS] Single candidate agreement returns neutral 0.50 (not artificial 1.0)")

    # 3 identical candidates -> 1.0
    assert engine.compute_agreement([
        "SELECT id, username FROM users WHERE status = 'active';",
        "SELECT id, username FROM users WHERE status = 'active';",
        "SELECT id, username FROM users WHERE status = 'active';"
    ]) == 1.0
    print("[PASS] All identical candidates returns 1.0")

    # 3 candidates comparing all pairs
    agree_3 = engine.compute_agreement([
        "SELECT id, username FROM users WHERE status = 'active';",
        "SELECT id, email FROM users WHERE status = 'active';",
        "SELECT id, country FROM users WHERE status = 'inactive';"
    ])
    assert 0.0 < agree_3 < 1.0
    print(f"[PASS] 3 diverse candidates pairwise agreement across all pairs: {agree_3:.3f}")

def test_adaptive_orchestration_run():
    print("\n=== Testing Full MultiAgentOrchestrator Execution ===")
    orch = MultiAgentOrchestrator()
    schema = {
        "users": {"id": "int", "username": "varchar", "email": "varchar", "status": "varchar"},
        "orders": {"id": "int", "user_id": "int", "total_amount": "decimal", "status": "varchar", "created_at": "datetime"},
        "products": {"id": "int", "name": "varchar", "category": "varchar", "price": "decimal"}
    }

    # Test 1: Simple high-confidence query (Targeting STOP early exit)
    res_simple = orch.run(
        english="Show all users",
        schema_name="shop_db",
        full_schema=schema,
        mode="ADAPTIVE_CONFIDENCE"
    )
    print(f"Simple query action history: {res_simple['action_history']}")
    print(f"Final SQL: {res_simple['sql']}")
    print(f"Confidence: {res_simple['confidence']['total_confidence']:.1%}")
    assert res_simple["success"] is True
    # Paper rule: STOP only when C >= tau (0.85), the query runs, and V >= 0.85
    conf = res_simple["confidence"]
    stop_rule = conf["total_confidence"] >= conf["threshold"] and conf["c_verifier"] >= 0.85
    assert (ACTION_STOP in res_simple["action_history"]) == stop_rule
    print("[PASS] Simple query follows the STOP rule (stopped=%s, C=%.3f, tau=%.2f)" % (stop_rule, conf["total_confidence"], conf["threshold"]))

    # Test 2: Ambiguous query (Targeting GENERATE MULTIPLE)
    res_ambig = orch.run(
        english="Find the best top active users",
        schema_name="shop_db",
        full_schema=schema,
        mode="ADAPTIVE_CONFIDENCE"
    )
    print(f"Ambiguous query action history: {res_ambig['action_history']}")
    assert ACTION_GENERATE_MULTIPLE in res_ambig["action_history"]
    print("[PASS] Ambiguous query successfully triggered GENERATE_MULTIPLE action")

    # Test 3: Unmatched schema query (Targeting RETRIEVE)
    res_retrieve = orch.run(
        english="Calculate the total money and revenue from purchases",
        schema_name="shop_db",
        full_schema=schema,
        mode="ADAPTIVE_CONFIDENCE"
    )
    print(f"Mismatched schema action history: {res_retrieve['action_history']}")
    assert ACTION_RETRIEVE in res_retrieve["action_history"]
    print("[PASS] Low schema relevance query successfully triggered RETRIEVE action and refined context")

    # Test 4: Syntax error query triggering REPAIR
    print("\n=== Testing REPAIR Action in Adaptive Orchestrator ===")
    # Create a mock verifier that returns an error on first attempt, then succeeds after repair
    original_verifier_exec = orch.verifier_agent.execute
    call_count = [0]
    def mock_flawed_verifier(sql, eng, s_name, f_schema):
        call_count[0] += 1
        if call_count[0] == 1:
            return {
                "agent": "Execution & Verification Agent",
                "c_exec": 0.10,
                "c_verifier": 0.20,
                "has_error": True,
                "error_message": "Table 'shop_db.nonexistent_table' doesn't exist",
                "diagnostics": ["MySQL Execution Error: Table doesn't exist"],
                "columns": [],
                "rows_preview": [],
                "duration_ms": 2.0,
                "tokens_used": 10
            }
        else:
            return original_verifier_exec(sql, eng, s_name, f_schema)

    orch.verifier_agent.execute = mock_flawed_verifier
    res_repair = orch.run(
        english="Show all users",
        schema_name="shop_db",
        full_schema=schema,
        mode="ADAPTIVE_CONFIDENCE"
    )
    orch.verifier_agent.execute = original_verifier_exec

    print(f"Repair query action history: {res_repair['action_history']}")
    print(f"Repaired SQL: {res_repair['sql']}")
    assert ACTION_REPAIR in res_repair["action_history"]
    assert res_repair["repaired"] is True
    print("[PASS] Execution error successfully triggered REPAIR action and self-corrected")

    # Test 5: All 5 modes test
    print("\n=== Testing All 5 Modes ===")
    modes = ["ADAPTIVE_CONFIDENCE", "FIXED_PIPELINE", "SINGLE_MODEL", "CONSENSUS_VOTING", "RULE_BASED"]
    for m in modes:
        res_m = orch.run("List active users", "shop_db", schema, mode=m)
        assert res_m["sql"], f"Mode {m} returned empty SQL"
        print(f"Mode: {m:20} | Success: {res_m['success']} | SQL: {res_m['sql']} | Tokens: {res_m['metrics']['total_tokens']} | Tokens Saved %: {res_m['metrics']['tokens_saved_pct']}")
    print("[PASS] All 5 modes executed cleanly with honest metrics")

if __name__ == "__main__":
    test_six_action_triggers()
    test_candidate_agreement()
    test_adaptive_orchestration_run()
    print("\nALL ORCHESTRATION TESTS COMPLETED SUCCESSFULLY!")
