"""Statistical evaluation and bootstrap CI module for Topic B4.

Only standard library used (math, random, json, argparse, pathlib).
Calculates:
1. Bootstrap 95% Confidence Intervals (resampling by claim).
2. Paired McNemar exact test (or binomial sign test) between shapes.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any


def bootstrap_ci(
    claim_trials: dict[str, list[bool]],
    *,
    num_samples: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, float]:
    """Calculate 95% Bootstrap Confidence Interval by resampling at the claim level.
    
    Args:
        claim_trials: mapping claim_id -> list of bool (results across seeds).
    """
    claim_ids = list(claim_trials.keys())
    if not claim_ids:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0}

    rng = random.Random(seed)
    bootstrap_means = []

    # Calculate empirical mean
    all_trials = [p for tests in claim_trials.values() for p in tests]
    mean = sum(all_trials) / len(all_trials) if all_trials else 0.0

    n_claims = len(claim_ids)
    for _ in range(num_samples):
        sampled_claims = [rng.choice(claim_ids) for _ in range(n_claims)]
        sample_trials = [p for c in sampled_claims for p in claim_trials[c]]
        if sample_trials:
            bootstrap_means.append(sum(sample_trials) / len(sample_trials))

    bootstrap_means.sort()
    lower_idx = int((alpha / 2.0) * len(bootstrap_means))
    upper_idx = int((1.0 - alpha / 2.0) * len(bootstrap_means))

    return {
        "mean": round(mean, 4),
        "ci_lower": round(bootstrap_means[lower_idx], 4),
        "ci_upper": round(bootstrap_means[upper_idx], 4),
    }


def mcnemar_exact_test(paired_outcomes: list[tuple[bool, bool]]) -> dict[str, Any]:
    """Calculate exact two-tailed McNemar p-value using binomial distribution.
    
    paired_outcomes: list of (shape_a_passed, shape_b_passed) on identical (claim, seed).
    b = A passed, B failed
    c = A failed, B passed
    Null hypothesis: P(b) == P(c) == 0.5 given n = b + c.
    """
    b = sum(1 for a, b_out in paired_outcomes if a and not b_out)
    c = sum(1 for a, b_out in paired_outcomes if not a and b_out)
    n = b + c

    if n == 0:
        return {"b": 0, "c": 0, "n_discordant": 0, "p_value": 1.0, "significant_at_05": False}

    # Two-sided binomial exact test with p = 0.5
    k = min(b, c)
    # Sum of Binomial(n, 0.5) for x in 0..k
    cumulative_prob = 0.0
    for x in range(k + 1):
        cumulative_prob += math.comb(n, x) * (0.5 ** n)
    p_value = min(1.0, 2.0 * cumulative_prob)

    return {
        "b_shape_a_only": b,
        "c_shape_b_only": c,
        "n_discordant": n,
        "p_value": round(p_value, 4),
        "significant_at_05": p_value < 0.05,
    }


def analyze_benchmark(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze benchmark.json containing trials across shapes."""
    raw_trials = data.get("trials", [])
    shapes_data: dict[str, dict[str, list[bool]]] = {}
    paired_index: dict[tuple[str, int], dict[str, bool]] = {}

    for t in raw_trials:
        s = t["shape"]
        cid = t["claim_id"]
        seed = t["seed"]
        passed = bool(t.get("passed", False))

        shapes_data.setdefault(s, {}).setdefault(cid, []).append(passed)
        paired_index.setdefault((cid, seed), {})[s] = passed

    # 1. Bootstrap CI for each shape
    ci_results = {}
    for s, claim_map in shapes_data.items():
        ci_results[s] = bootstrap_ci(claim_map)

    # 2. McNemar pairwise tests against workflow (baseline)
    comparisons = {}
    baseline_shape = "workflow" if "workflow" in shapes_data else list(shapes_data.keys())[0]
    for s in shapes_data:
        if s == baseline_shape:
            continue
        pairs = []
        for pair_key, shape_res in paired_index.items():
            if baseline_shape in shape_res and s in shape_res:
                pairs.append((shape_res[baseline_shape], shape_res[s]))
        comparisons[f"{baseline_shape}_vs_{s}"] = mcnemar_exact_test(pairs)

    return {
        "confidence_intervals_95": ci_results,
        "mcnemar_paired_tests": comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Statistical tests for Topic B4")
    parser.add_argument("--in", dest="in_path", default="reports/benchmark.json")
    parser.add_argument("--out", dest="out_path", default="reports/bonus_stats.json")
    args = parser.parse_args()

    in_file = Path(args.in_path)
    if not in_file.exists():
        raise FileNotFoundError(f"Input file not found: {in_file}")

    with in_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    results = analyze_benchmark(data)
    out_file = Path(args.out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"B4 Statistical Analysis complete. Saved to: {out_file}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
