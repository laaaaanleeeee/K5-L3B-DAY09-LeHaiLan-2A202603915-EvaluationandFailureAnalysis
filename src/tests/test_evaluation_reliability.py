"""Crash/retry with capped refunds, shared by all four shapes.

Run from src: python -m pytest -q -m student -o addopts= tests/test_evaluation_reliability.py -k swarm
The three student shapes are expected to fail until implemented.
"""

import time

import pytest

from lab8.db import connect
from lab8.durability import InjectedCrash, committed_audit_count, get_refund
from lab8.metrics import trial_pass
from lab8.shapes import SHAPES
from tests.conftest import BY_ID


@pytest.mark.student
@pytest.mark.parametrize("shape", ["workflow", "single", "orchestrator", "swarm"])
@pytest.mark.parametrize(
    "claim_id,quote,amount",
    [("C-008", 35000, 20000), ("C-014", 150000, 120000)],
    ids=["approval-cap", "order-top-up"],
)
@pytest.mark.parametrize(
    "point",
    ["before_effect", "after_effect_before_checkpoint", "after_checkpoint"],
)
def test_capped_refund_survives_crash_and_repeated_resume(
    public_db, shape, claim_id, quote, amount, point
):
    run = SHAPES[shape]
    with pytest.raises(InjectedCrash, match=point):
        run(claim_id, seed=11, store_path=str(public_db), crash_at=point)

    # Inspect persisted state through a new connection, not the crashed caller's.
    conn = connect(public_db)
    try:
        effect = get_refund(conn, claim_id)
        committed = point != "before_effect"
        assert committed_audit_count(conn, claim_id) == int(committed)
        if committed:
            assert effect is not None
            assert effect["amount_vnd"] == amount
        else:
            assert effect is None
        checkpoint = conn.execute(
            "SELECT 1 FROM checkpoints WHERE claim_id = ? AND step = 'issue_refund'",
            (claim_id,),
        ).fetchone()
        assert (checkpoint is not None) == (point == "after_checkpoint")
    finally:
        conn.close()

    for _ in range(2):
        started_at = time.time()
        result = run(claim_id, seed=11, store_path=str(public_db))
        assert result.status == "resolved"
        assert result.proposal_amount == quote  # Full quote, not the capped effect.
        conn = connect(public_db)
        try:
            passed, reason = trial_pass(
                result.as_dict(), BY_ID[claim_id]["expected"], conn,
                started_at=started_at,
            )
            assert passed, reason
            assert get_refund(conn, claim_id)["amount_vnd"] == amount
            assert committed_audit_count(conn, claim_id) == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM refund_ledger WHERE claim_id = ?", (claim_id,)
            ).fetchone()[0] == 1
            assert conn.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE claim_id = ? AND step = 'issue_refund'",
                (claim_id,),
            ).fetchone()[0] == 1
        finally:
            conn.close()
