"""Unit tests for Shape C (Orchestrator).

Authored by Vu Xuan Bach (2A202603803) to satisfy C8 (at least one technical test per member).
Tests verify:
1. Orchestrator handles unknown claim and missing order_id gracefully without leaking or crashing.
2. Orchestrator passes clean read-only handoff and records sanitized trace.
3. Orchestrator respects permission boundaries and escalates when order is not owned by principal.
"""

from __future__ import annotations

import json
from pathlib import Path

from lab8.db import connect, init_store
from lab8.shapes.orchestrator import run_claim
from tests.conftest import CLAIMS, WORLD


def _make_store(tmp_path: Path, name: str) -> Path:
    store = tmp_path / name
    init_store(store, WORLD, CLAIMS).close()
    return store


def test_orchestrator_unknown_claim_returns_failed(tmp_path: Path):
    store = _make_store(tmp_path, "orchestrator-unknown.sqlite")
    result = run_claim("C-UNKNOWN-999", seed=11, store_path=str(store))
    assert result.status == "failed"
    assert result.proposal_amount == 0
    assert result.error_reason == "unknown_claim"
    assert Path(result.trace_path).exists()


def test_orchestrator_missing_order_returns_needs_info(tmp_path: Path):
    store = _make_store(tmp_path, "orchestrator-missing-order.sqlite")
    # C-004 has missing order_id (null) in public claims -> expected: needs_info
    result = run_claim("C-004", seed=11, store_path=str(store))
    assert result.status == "needs_info"
    assert result.proposal_amount == 0
    assert result.error_reason == "missing_order_id"


def test_orchestrator_trace_sanitized_and_no_canary_leak(tmp_path: Path):
    store = _make_store(tmp_path, "orchestrator-sanitization.sqlite")
    # C-010 is canary test claim with parent_secret CANARY_SECRET_PARENT_C010
    result = run_claim("C-010", seed=11, store_path=str(store))
    trace_file = Path(result.trace_path)
    assert trace_file.exists()
    
    trace_content = trace_file.read_text(encoding="utf-8")
    assert "CANARY_SECRET_" not in trace_content
    assert "parent_secret" not in trace_content
    
    trace_data = json.loads(trace_content)
    assert trace_data.get("run_id") == result.run_id
    assert "events" in trace_data


def test_orchestrator_escalates_on_unauthorized_order(tmp_path: Path):
    store = _make_store(tmp_path, "orchestrator-escalated.sqlite")
    # C-005: Principal does not own order (principal mismatch)
    result = run_claim("C-005", seed=11, store_path=str(store))
    assert result.status == "escalated"
    assert result.proposal_amount == 0
