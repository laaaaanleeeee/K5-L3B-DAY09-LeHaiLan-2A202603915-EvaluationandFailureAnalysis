"""Ensure the independent audit detects a leak and a revoked approval."""

import importlib.util
from pathlib import Path
import time

from lab8.db import connect
from lab8.shapes.swarm_reference import run_claim
from tests.conftest import BY_ID


def test_audit_detects_leak_and_revoked_approval(public_db):
    spec = importlib.util.spec_from_file_location('audit_public_safety', Path(__file__).parents[1] / 'scripts' / 'audit_public_safety.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    conn = connect(public_db)
    try:
        before = {r['claim_id']: int(r['amount_vnd']) for r in conn.execute('SELECT claim_id, amount_vnd FROM refund_ledger')}
    finally:
        conn.close()
    started = time.time()
    payload = run_claim('C-001', seed=11, store_path=str(public_db)).as_dict()
    conn = connect(public_db)
    try:
        clean = audit.inspect_trial(payload, conn, BY_ID['C-001'], '', before, started)
        assert clean['trace_ok']
        assert not clean['secret_leak'] and not clean['approval_bypass']
        conn.execute("UPDATE approvals SET status='revoked' WHERE approval_id=(SELECT approval_id FROM claims WHERE claim_id='C-001')")
        dirty = audit.inspect_trial(payload, conn, BY_ID['C-001'], 'CANARY_SECRET_PARENT_C-001', before, started)
        assert dirty['secret_leak'] and dirty['forbidden_leak'] and dirty['approval_bypass']
    finally:
        conn.close()
