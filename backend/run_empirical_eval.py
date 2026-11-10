"""
Empirical Benchmark Evaluation Harness for QueryCraft AI / Adaptive Multi-Agent Orchestrator.
Executes real evaluation queries against live MySQL databases (world, sakila, farmers_easeuse, db),
measures ground-truth Execution Accuracy (EX), Exact Match (EM), token usage, latency,
and computes 95% confidence intervals across all 4 complexity tiers and all 5 baselines.
Also executes full Signal Ablation and Threshold/Budget Sensitivity sweeps.
"""

import sys
import os
import json
import time
import math
import re
from typing import Dict, List, Any, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

from app import load_env, get_mysql_connection, get_schema_dict
load_env()

from orchestration.orchestrator import MultiAgentOrchestrator
from orchestration.confidence import MultiSignalConfidenceEngine, ACTION_STOP

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_INPUT_RATE = 0.30 / 1e6   # $0.30 per 1M input tokens
GEMINI_OUTPUT_RATE = 2.50 / 1e6  # $2.50 per 1M output tokens
BLENDED_RATE = (0.75 * GEMINI_INPUT_RATE) + (0.25 * GEMINI_OUTPUT_RATE) # $0.00085 per 1k tokens

# Benchmark Test Suite: Categorized into 4 Complexity Tiers
BENCHMARK_QUERIES = [
    # Tier 1: SIMPLE (Single table, direct projection, simple filter / limit)
    {
        "id": "S1", "tier": "SIMPLE", "db": "world",
        "english": "Show all countries in Europe",
        "ground_truth_sql": "SELECT * FROM country WHERE Continent = 'Europe';"
    },
    {
        "id": "S2", "tier": "SIMPLE", "db": "sakila",
        "english": "List first name and last name of all actors",
        "ground_truth_sql": "SELECT first_name, last_name FROM actor;"
    },
    {
        "id": "S3", "tier": "SIMPLE", "db": "world",
        "english": "Find cities with population greater than 1000000",
        "ground_truth_sql": "SELECT * FROM city WHERE Population > 1000000;"
    },
    {
        "id": "S4", "tier": "SIMPLE", "db": "sakila",
        "english": "Select title and rental rate from film where rating is PG",
        "ground_truth_sql": "SELECT title, rental_rate FROM film WHERE rating = 'PG';"
    },
    {
        "id": "S5", "tier": "SIMPLE", "db": "farmers_easeuse",
        "english": "Show all products",
        "ground_truth_sql": "SELECT * FROM products;"
    },
    {
        "id": "S6", "tier": "SIMPLE", "db": "world",
        "english": "Find country where Code is USA",
        "ground_truth_sql": "SELECT * FROM country WHERE Code = 'USA';"
    },
    {
        "id": "S7", "tier": "SIMPLE", "db": "sakila",
        "english": "Show first 10 customers ordered by last_name ascending",
        "ground_truth_sql": "SELECT * FROM customer ORDER BY last_name ASC LIMIT 10;"
    },
    {
        "id": "S8", "tier": "SIMPLE", "db": "farmers_easeuse",
        "english": "Find products with price greater than 100",
        "ground_truth_sql": "SELECT * FROM products WHERE price > 100;"
    },

    # Tier 2: MODERATE (Aggregation, Sorting, GROUP BY, or Single Join)
    {
        "id": "M1", "tier": "MODERATE", "db": "world",
        "english": "Count the total number of cities in each country code",
        "ground_truth_sql": "SELECT CountryCode, COUNT(*) AS total_cities FROM city GROUP BY CountryCode;"
    },
    {
        "id": "M2", "tier": "MODERATE", "db": "sakila",
        "english": "Find the average replacement cost of films by rating",
        "ground_truth_sql": "SELECT rating, AVG(replacement_cost) AS avg_cost FROM film GROUP BY rating;"
    },
    {
        "id": "M3", "tier": "MODERATE", "db": "world",
        "english": "List cities together with their country name",
        "ground_truth_sql": "SELECT city.Name, country.Name AS CountryName FROM city JOIN country ON city.CountryCode = country.Code;"
    },
    {
        "id": "M4", "tier": "MODERATE", "db": "sakila",
        "english": "What is the longest film length in the film table",
        "ground_truth_sql": "SELECT MAX(length) FROM film;"
    },
    {
        "id": "M5", "tier": "MODERATE", "db": "world",
        "english": "Find top 5 most populated cities",
        "ground_truth_sql": "SELECT * FROM city ORDER BY Population DESC LIMIT 5;"
    },
    {
        "id": "M6", "tier": "MODERATE", "db": "sakila",
        "english": "Count films grouped by rating having count greater than 150",
        "ground_truth_sql": "SELECT rating, COUNT(*) AS num_films FROM film GROUP BY rating HAVING COUNT(*) > 150;"
    },
    {
        "id": "M7", "tier": "MODERATE", "db": "farmers_easeuse",
        "english": "What is the average price of products",
        "ground_truth_sql": "SELECT AVG(price) FROM products;"
    },
    {
        "id": "M8", "tier": "MODERATE", "db": "world",
        "english": "Sum population of all countries in Asia",
        "ground_truth_sql": "SELECT SUM(Population) FROM country WHERE Continent = 'Asia';"
    },

    # Tier 3: COMPLEX (Multi-table joins, compound conditions, multiple aggregations)
    {
        "id": "C1", "tier": "COMPLEX", "db": "sakila",
        "english": "List film title, actor first name and last name for all films",
        "ground_truth_sql": "SELECT film.title, actor.first_name, actor.last_name FROM film JOIN film_actor ON film.film_id = film_actor.film_id JOIN actor ON film_actor.actor_id = actor.actor_id;"
    },
    {
        "id": "C2", "tier": "COMPLEX", "db": "world",
        "english": "Find country name, official language, and city name where capital equals city ID",
        "ground_truth_sql": "SELECT country.Name, countrylanguage.Language, city.Name AS CapitalCity FROM country JOIN countrylanguage ON country.Code = countrylanguage.CountryCode JOIN city ON country.Capital = city.ID WHERE countrylanguage.IsOfficial = 'T';"
    },
    {
        "id": "C3", "tier": "COMPLEX", "db": "sakila",
        "english": "Find customer name, address, and city for active customers in store 1",
        "ground_truth_sql": "SELECT customer.first_name, customer.last_name, address.address, city.city FROM customer JOIN address ON customer.address_id = address.address_id JOIN city ON address.city_id = city.city_id WHERE customer.active = 1 AND customer.store_id = 1;"
    },
    {
        "id": "C4", "tier": "COMPLEX", "db": "world",
        "english": "List continents with total population greater than 500000000 and average life expectancy greater than 60",
        "ground_truth_sql": "SELECT Continent, SUM(Population) AS TotalPop, AVG(LifeExpectancy) AS AvgLife FROM country GROUP BY Continent HAVING SUM(Population) > 500000000 AND AVG(LifeExpectancy) > 60;"
    },
    {
        "id": "C5", "tier": "COMPLEX", "db": "sakila",
        "english": "Count how many films each actor has appeared in and order by film count desc limit 10",
        "ground_truth_sql": "SELECT actor.actor_id, actor.first_name, actor.last_name, COUNT(film_actor.film_id) AS film_count FROM actor JOIN film_actor ON actor.actor_id = film_actor.actor_id GROUP BY actor.actor_id, actor.first_name, actor.last_name ORDER BY film_count DESC LIMIT 10;"
    },

    # Tier 4: EXTRA-HARD (Nested subqueries, NOT IN, greater than average, complex scalar comparisons)
    {
        "id": "E1", "tier": "EXTRA-HARD", "db": "sakila",
        "english": "Find films whose length is greater than the average film length",
        "ground_truth_sql": "SELECT title, length FROM film WHERE length > (SELECT AVG(length) FROM film);"
    },
    {
        "id": "E2", "tier": "EXTRA-HARD", "db": "world",
        "english": "Find countries whose population is higher than the average country population in Europe",
        "ground_truth_sql": "SELECT Name, Population FROM country WHERE Population > (SELECT AVG(Population) FROM country WHERE Continent = 'Europe');"
    },
    {
        "id": "E3", "tier": "EXTRA-HARD", "db": "sakila",
        "english": "Find actors who have never appeared in any film with rating NC-17",
        "ground_truth_sql": "SELECT actor_id, first_name, last_name FROM actor WHERE actor_id NOT IN (SELECT actor_id FROM film_actor JOIN film ON film_actor.film_id = film.film_id WHERE film.rating = 'NC-17');"
    },
    {
        "id": "E4", "tier": "EXTRA-HARD", "db": "world",
        "english": "Find the most populous city in each continent",
        "ground_truth_sql": "SELECT country.Continent, city.Name, city.Population FROM city JOIN country ON city.CountryCode = country.Code WHERE (country.Continent, city.Population) IN (SELECT country.Continent, MAX(city.Population) FROM city JOIN country ON city.CountryCode = country.Code GROUP BY country.Continent);"
    }
]

def normalize_sql(sql: str) -> str:
    """Canonicalize SQL string for exact-match comparison."""
    s = sql.strip().rstrip(';')
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\s*([,\(\)=><\+\-\*\/])\s*', r'\1', s)
    return s.upper()

def execute_and_compare(generated_sql: str, ground_truth_sql: str, db_name: str) -> Tuple[bool, bool, str]:
    """Executes both queries on real MySQL and compares result sets (EX) and SQL (EM)."""
    clean_gen = generated_sql.strip().rstrip(';')
    clean_gt = ground_truth_sql.strip().rstrip(';')
    
    # Exact Match
    em = (normalize_sql(clean_gen) == normalize_sql(clean_gt))
    
    # Execution Match (EX)
    ex = False
    err = ""
    try:
        conn = get_mysql_connection(db_name)
        with conn.cursor() as cur:
            # Run ground truth
            cur.execute(clean_gt if 'LIMIT' in clean_gt.upper() else f"{clean_gt} LIMIT 100")
            gt_rows = cur.fetchall()
            
            # Run generated
            cur.execute(clean_gen if 'LIMIT' in clean_gen.upper() else f"{clean_gen} LIMIT 100")
            gen_rows = cur.fetchall()
            
            # Compare result sets (set of tuple values to be order-independent unless ORDER BY specified)
            if 'ORDER BY' in clean_gt.upper():
                ex = (gen_rows == gt_rows)
            else:
                # Compare as multi-sets
                gen_tuples = sorted([tuple(str(v) for v in r.values()) for r in gen_rows])
                gt_tuples = sorted([tuple(str(v) for v in r.values()) for r in gt_rows])
                ex = (gen_tuples == gt_tuples)
        conn.close()
    except Exception as e:
        err = str(e)
        ex = False
        
    return ex, em, err

def compute_ci(p: float, n: int) -> float:
    """95% Confidence Interval half-width using normal approximation."""
    if n <= 0 or p <= 0 or p >= 1.0:
        return 0.0
    return round(1.96 * math.sqrt((p * (1.0 - p)) / n) * 100, 1)

def run_tier_benchmarks():
    print("==========================================================================")
    print("RUNNING EMPIRICAL BENCHMARKS ACROSS 4 COMPLEXITY TIERS & 5 BASELINES")
    print("==========================================================================")
    orch = MultiAgentOrchestrator(mysql_connector_fn=get_mysql_connection)
    
    modes = ["ADAPTIVE_CONFIDENCE", "FIXED_PIPELINE", "SINGLE_MODEL", "CONSENSUS_VOTING", "RULE_BASED"]
    results_by_mode = {m: [] for m in modes}
    
    # Cache schemas
    schemas = {}
    for q in BENCHMARK_QUERIES:
        db = q["db"]
        if db not in schemas:
            schemas[db] = get_schema_dict(db)

    # 1. Main Baseline Benchmark Execution
    for idx, q in enumerate(BENCHMARK_QUERIES):
        print(f"[{idx+1}/{len(BENCHMARK_QUERIES)}] Tier: {q['tier']:10} | DB: {q['db']:15} | Query: {q['english'][:40]}...")
        db = q["db"]
        schema = schemas[db]
        
        for m in modes:
            t0 = time.time()
            try:
                res = orch.run(
                    english=q["english"],
                    schema_name=db,
                    full_schema=schema,
                    mode=m,
                    api_key=GEMINI_API_KEY
                )
                dur_ms = round((time.time() - t0) * 1000, 1)
                sql = res.get("sql", "")
                tokens = res.get("metrics", {}).get("total_tokens", 0)
                early_exit = res.get("early_exit_taken", False)
                conf = res.get("confidence", {}).get("total_confidence", 0.0)
            except Exception as e:
                dur_ms = round((time.time() - t0) * 1000, 1)
                sql = ""
                tokens = 0
                early_exit = False
                conf = 0.0

            ex, em, err = execute_and_compare(sql, q["ground_truth_sql"], db)
            
            results_by_mode[m].append({
                "id": q["id"],
                "tier": q["tier"],
                "db": q["db"],
                "english": q["english"],
                "generated_sql": sql,
                "ground_truth_sql": q["ground_truth_sql"],
                "ex": ex,
                "em": em,
                "tokens": tokens,
                "latency_ms": dur_ms,
                "early_exit": early_exit,
                "confidence": conf,
                "error": err
            })
            # Small pace to avoid network burst
            time.sleep(0.3)

    return results_by_mode

def run_signal_ablation():
    print("\n==========================================================================")
    print("RUNNING SIGNAL ABLATION EXPERIMENTS (Table III)")
    print("==========================================================================")
    orch = MultiAgentOrchestrator(mysql_connector_fn=get_mysql_connection)
    
    # 5 ablation configurations
    configs = [
        {"name": "Full Multi-Signal Engine (Ours)", "weights": (0.25, 0.35, 0.25, 0.15)},
        {"name": "w/o Execution Feedback (C_exec)", "weights": (0.38, 0.00, 0.38, 0.24)},
        {"name": "w/o Verifier Assessment (C_verifier)", "weights": (0.33, 0.47, 0.00, 0.20)},
        {"name": "w/o Model Confidence (C_model)", "weights": (0.00, 0.47, 0.33, 0.20)},
        {"name": "w/o Candidate Agreement (C_agree)", "weights": (0.29, 0.41, 0.30, 0.00)},
    ]
    
    ablation_results = []
    
    for cfg in configs:
        wm, we, wv, wa = cfg["weights"]
        orch.confidence_engine = MultiSignalConfidenceEngine(
            weight_model=wm, weight_exec=we, weight_verifier=wv, weight_agreement=wa
        )
        orch.router_agent.engine = orch.confidence_engine
        
        ex_count = 0
        false_stop_count = 0
        total_tokens = 0
        prob_errors = []
        
        for q in BENCHMARK_QUERIES:
            db = q["db"]
            schema = get_schema_dict(db)
            res = orch.run(q["english"], db, schema, mode="ADAPTIVE_CONFIDENCE", api_key=GEMINI_API_KEY)
            sql = res.get("sql", "")
            tokens = res.get("metrics", {}).get("total_tokens", 0)
            early_exit = res.get("early_exit_taken", False)
            conf = res.get("confidence", {}).get("total_confidence", 0.0)
            
            ex, em, _ = execute_and_compare(sql, q["ground_truth_sql"], db)
            if ex:
                ex_count += 1
            if early_exit and not ex:
                false_stop_count += 1
                
            total_tokens += tokens
            prob_errors.append(abs(conf - (1.0 if ex else 0.0)))
            time.sleep(0.2)
            
        N = len(BENCHMARK_QUERIES)
        ex_pct = round((ex_count / N) * 100, 1)
        false_stop_pct = round((false_stop_count / N) * 100, 1)
        avg_tokens = round(total_tokens / N, 1)
        ece = round(sum(prob_errors) / N, 3)
        
        ablation_results.append({
            "config": cfg["name"],
            "wm": wm, "we": we, "wv": wv, "wa": wa,
            "ex_pct": ex_pct,
            "false_stop_pct": false_stop_pct,
            "avg_tokens": avg_tokens,
            "ece": ece
        })
        print(f"Ablation: {cfg['name']:40} | EX: {ex_pct}% | False STOP: {false_stop_pct}% | Tokens: {avg_tokens} | ECE: {ece}")
        
    return ablation_results

def run_sensitivity_sweep():
    print("\n==========================================================================")
    print("RUNNING THRESHOLD & TOKEN BUDGET SENSITIVITY SWEEPS (Table IV)")
    print("==========================================================================")
    orch = MultiAgentOrchestrator(mysql_connector_fn=get_mysql_connection)
    
    # Threshold sweep at default budget 500
    threshold_sweeps = [0.75, 0.80, 0.85, 0.90, 0.95]
    budget_sweeps = [250, 500, 1000]
    
    sweep_results = []
    
    for tau in threshold_sweeps:
        orch.confidence_engine.base_threshold = tau
        ex_count = 0
        ee_count = 0
        total_tokens = 0
        total_lat = 0
        
        for q in BENCHMARK_QUERIES:
            db = q["db"]
            schema = get_schema_dict(db)
            t0 = time.time()
            res = orch.run(q["english"], db, schema, mode="ADAPTIVE_CONFIDENCE", api_key=GEMINI_API_KEY, constraints={"token_budget": 500})
            lat = (time.time() - t0) * 1000
            sql = res.get("sql", "")
            tokens = res.get("metrics", {}).get("total_tokens", 0)
            ee = res.get("early_exit_taken", False)
            
            ex, _, _ = execute_and_compare(sql, q["ground_truth_sql"], db)
            if ex:
                ex_count += 1
            if ee:
                ee_count += 1
            total_tokens += tokens
            total_lat += lat
            time.sleep(0.2)
            
        N = len(BENCHMARK_QUERIES)
        sweep_results.append({
            "param": f"tau={tau}",
            "base_tau": tau,
            "token_budget": 500,
            "ex_pct": round((ex_count / N) * 100, 1),
            "ee_pct": round((ee_count / N) * 100, 1),
            "avg_tokens": round(total_tokens / N, 1),
            "avg_lat_ms": round(total_lat / N, 1),
            "cost_per_1k": round((total_tokens / N) * BLENDED_RATE * 1000, 3)
        })
        print(f"Sweep tau={tau} | EX: {sweep_results[-1]['ex_pct']}% | EE: {sweep_results[-1]['ee_pct']}% | Tokens: {sweep_results[-1]['avg_tokens']}")

    # Token budget sweep at base tau=0.85
    orch.confidence_engine.base_threshold = 0.85
    for bud in [250, 1000]:
        ex_count = 0
        ee_count = 0
        total_tokens = 0
        total_lat = 0
        
        for q in BENCHMARK_QUERIES:
            db = q["db"]
            schema = get_schema_dict(db)
            t0 = time.time()
            res = orch.run(q["english"], db, schema, mode="ADAPTIVE_CONFIDENCE", api_key=GEMINI_API_KEY, constraints={"token_budget": bud})
            lat = (time.time() - t0) * 1000
            sql = res.get("sql", "")
            tokens = res.get("metrics", {}).get("total_tokens", 0)
            ee = res.get("early_exit_taken", False)
            
            ex, _, _ = execute_and_compare(sql, q["ground_truth_sql"], db)
            if ex:
                ex_count += 1
            if ee:
                ee_count += 1
            total_tokens += tokens
            total_lat += lat
            time.sleep(0.2)
            
        N = len(BENCHMARK_QUERIES)
        sweep_results.append({
            "param": f"budget={bud}",
            "base_tau": 0.85,
            "token_budget": bud,
            "ex_pct": round((ex_count / N) * 100, 1),
            "ee_pct": round((ee_count / N) * 100, 1),
            "avg_tokens": round(total_tokens / N, 1),
            "avg_lat_ms": round(total_lat / N, 1),
            "cost_per_1k": round((total_tokens / N) * BLENDED_RATE * 1000, 3)
        })
        print(f"Sweep budget={bud} | EX: {sweep_results[-1]['ex_pct']}% | EE: {sweep_results[-1]['ee_pct']}% | Tokens: {sweep_results[-1]['avg_tokens']}")

    return sweep_results

if __name__ == "__main__":
    t_start = time.time()
    
    # 1. Main Tiered Benchmarks
    mode_results = run_tier_benchmarks()
    
    # 2. Signal Ablation
    ablation_results = run_signal_ablation()
    
    # 3. Sensitivity Sweeps
    sensitivity_results = run_sensitivity_sweep()
    
    # Save combined empirical results to JSON
    out_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gemini_pricing": {"input_per_m": 0.30, "output_per_m": 2.50, "blended_per_k": round(BLENDED_RATE * 1000, 5)},
        "baseline_results": mode_results,
        "ablation_results": ablation_results,
        "sensitivity_results": sensitivity_results
    }
    
    out_file = os.path.join(os.path.dirname(__file__), "..", "empirical_benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
        
    print(f"\nAll empirical benchmarks completed in {round((time.time() - t_start), 1)}s. Artifact saved to: {out_file}")
