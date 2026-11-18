"""Failure handling and safety checks specific to shape B."""

import json

from lab8.db import connect
from lab8.shapes import single


def test_single_model_failure_is_safe_and_does_not_write(public_db, monkeypatch):
    def broken_model(*args, **kwargs):
        raise ValueError("CANARY_SECRET_PARENT_C-001")

    monkeypatch.setattr(single, "complete", broken_model)
    result = single.run_claim("C-001", seed=11, store_path=str(public_db))

    assert result.status == "failed"
    assert result.error_reason == "agent_error:ValueError"
    assert result.refund_effects == []
    trace = json.loads(open(result.trace_path, encoding="utf-8").read())
    assert trace["run_id"] == result.run_id
    assert "CANARY_SECRET_" not in json.dumps(trace)
    conn = connect(public_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM refund_ledger WHERE claim_id = 'C-001'").fetchone()[0] == 0
    finally:
        conn.close()


def test_single_uses_bounded_read_tools_and_full_quote(public_db):
    result = single.run_claim("C-014", seed=55, store_path=str(public_db))

    assert result.status == "resolved"
    assert result.proposal_amount == 150000
    assert result.refund_effects[0]["amount_vnd"] == 120000
    assert result.model_calls <= 8
    trace = json.loads(open(result.trace_path, encoding="utf-8").read())
    called = [event["payload"]["name"] for event in trace["events"] if event["kind"] == "tool_call"]
    assert called == ["lookup_order", "lookup_policy", "lookup_refund_history", "compute_compensation"]
    assert "issue_refund" not in called
