import json
import math

with open('empirical_benchmark_results.json') as f:
    d = json.load(f)

base = d['baseline_results']
print('=== BASELINE OVERALL METRICS ===')
for m, runs in base.items():
    N = len(runs)
    ex_cnt = sum(1 for r in runs if r['ex'])
    em_cnt = sum(1 for r in runs if r['em'])
    tok_avg = sum(r['tokens'] for r in runs) / N
    lat_avg = sum(r['latency_ms'] for r in runs) / N
    ee_cnt = sum(1 for r in runs if r['early_exit'])
    cost = tok_avg * 0.00085
    ci_ex = 1.96 * math.sqrt((ex_cnt/N * (1 - ex_cnt/N)) / N) * 100 if 0 < ex_cnt < N else 0.0
    ci_em = 1.96 * math.sqrt((em_cnt/N * (1 - em_cnt/N)) / N) * 100 if 0 < em_cnt < N else 0.0
    print(f'{m:20} | EX: {ex_cnt/N*100:5.1f}% (+-{ci_ex:4.1f}) | EM: {em_cnt/N*100:5.1f}% (+-{ci_em:4.1f}) | Tokens: {tok_avg:6.1f} | Cost: ${cost:6.3f} | Latency: {lat_avg:6.1f}ms | EE: {ee_cnt/N*100:4.1f}%')

print('\n=== ADAPTIVE_CONFIDENCE BY TIER ===')
adaptive_runs = base['ADAPTIVE_CONFIDENCE']
tiers = ['SIMPLE', 'MODERATE', 'COMPLEX', 'EXTRA-HARD']
for t in tiers:
    t_runs = [r for r in adaptive_runs if r['tier'] == t]
    N = len(t_runs)
    ex_cnt = sum(1 for r in t_runs if r['ex'])
    em_cnt = sum(1 for r in t_runs if r['em'])
    tok_avg = sum(r['tokens'] for r in t_runs) / N
    lat_avg = sum(r['latency_ms'] for r in t_runs) / N
    ee_cnt = sum(1 for r in t_runs if r['early_exit'])
    cost = tok_avg * 0.00085
    ci_ex = 1.96 * math.sqrt((ex_cnt/N * (1 - ex_cnt/N)) / N) * 100 if 0 < ex_cnt < N else 0.0
    ci_em = 1.96 * math.sqrt((em_cnt/N * (1 - em_cnt/N)) / N) * 100 if 0 < em_cnt < N else 0.0
    print(f'{t:12} (N={N}) | EX: {ex_cnt/N*100:5.1f}% (+-{ci_ex:4.1f}) | EM: {em_cnt/N*100:5.1f}% (+-{ci_em:4.1f}) | Tokens: {tok_avg:6.1f} | Cost: ${cost:6.3f} | Latency: {lat_avg:6.1f}ms | EE: {ee_cnt/N*100:4.1f}%')

print('\n=== ABLATION RESULTS (Table III) ===')
for a in d['ablation_results']:
    cfg = a['config']
    ex_p = a['ex_pct']
    fs_p = a['false_stop_pct']
    tok = a['avg_tokens']
    ece = a['ece']
    print(f'{cfg:40} | EX: {ex_p:5.1f}% | False STOP: {fs_p:4.1f}% | Tokens: {tok:5.1f} | ECE: {ece}')

print('\n=== SENSITIVITY SWEEP (Table IV) ===')
for s in d['sensitivity_results']:
    param = s['param']
    ex_p = s['ex_pct']
    ee_p = s['ee_pct']
    tok = s['avg_tokens']
    lat = s['avg_lat_ms']
    cst = s['cost_per_1k']
    print(f'{param:15} | EX: {ex_p:5.1f}% | EE: {ee_p:4.1f}% | Tokens: {tok:5.1f} | Latency: {lat:6.1f}ms | Cost: ${cst:5.3f}')
