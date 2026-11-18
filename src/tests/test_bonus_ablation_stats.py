"""Unit tests for Topic B4 (Baseline, Ablation and Statistical Evaluation)."""

from __future__ import annotations

import json
from pathlib import Path

from bonus.stats import analyze_benchmark, bootstrap_ci, mcnemar_exact_test


def test_bootstrap_ci_bounds():
    # Synthetic claim trials: 10 claims, 8 always pass, 2 always fail
    claim_trials = {f"C-{i:03d}": [True] * 5 for i in range(1, 9)}
    claim_trials.update({f"C-{i:03d}": [False] * 5 for i in range(9, 11)})

    ci = bootstrap_ci(claim_trials, num_samples=500, seed=123)
    assert ci["mean"] == 0.8
    assert 0.0 <= ci["ci_lower"] <= ci["mean"] <= ci["ci_upper"] <= 1.0


def test_mcnemar_identical_shapes_yields_p_one():
    # Both shapes pass or fail together
    pairs = [(True, True)] * 30 + [(False, False)] * 10
    res = mcnemar_exact_test(pairs)
    assert res["n_discordant"] == 0
    assert res["p_value"] == 1.0
    assert not res["significant_at_05"]


def test_mcnemar_detects_discordance():
    # Shape A passes 10 times where Shape B fails
    pairs = [(True, False)] * 10 + [(True, True)] * 40
    res = mcnemar_exact_test(pairs)
    assert res["b_shape_a_only"] == 10
    assert res["c_shape_b_only"] == 0
    assert res["n_discordant"] == 10
    assert res["p_value"] < 0.05
    assert res["significant_at_05"]


def test_analyze_benchmark_runs_on_live_data(tmp_path: Path):
    benchmark_file = Path("reports/benchmark.json")
    if not benchmark_file.exists():
        return  # Skip if not yet run
    with benchmark_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    results = analyze_benchmark(data)
    assert "confidence_intervals_95" in results
    assert "mcnemar_paired_tests" in results
    assert "workflow" in results["confidence_intervals_95"]
