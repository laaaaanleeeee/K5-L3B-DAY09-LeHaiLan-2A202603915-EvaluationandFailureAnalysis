"""Ablation tests; this is not a claim to completion of a bonus topic."""

import pytest

from lab8.db import connect
from lab8.metrics import trial_pass
from tests.conftest import BY_ID


@pytest.mark.parametrize("claim_id", ["C-002", "C-001"])
def test_no_override_uses_order_facts(public_db, claim_id):
    from bonus.swarm_no_override import run_claim

    result = run_claim(claim_id, seed=55, store_path=str(public_db))
    conn = connect(public_db)
    try:
        passed, reason = trial_pass(result.as_dict(), BY_ID[claim_id]["expected"], conn)
        assert passed, reason
    finally:
        conn.close()


def test_variant_only_disables_override_and_renames_trace():
    import inspect

    from bonus import swarm_no_override
    from lab8.shapes import swarm_reference

    original = inspect.getsource(swarm_reference._run)
    expected = original.replace('"swarm"', '"swarm_no_override"').replace(
        'if parsed_delay is not None and parsed_delay != int(order["delay_days"]) and seed % 5 == 0:',
        'if False:  # Ablation: ticket must not override structured order facts.',
    )
    assert inspect.getsource(swarm_no_override._run) == expected
