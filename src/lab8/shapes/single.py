"""Shape B — one ReAct agent. Student work.

Use `lab8.runtime.run_react` with max_steps=8. `decide` may pick a read tool.
It must not call `issue_refund`. After the loop, the host validates the quote
and is the only writer.

A decide() that trusts ticket text over the order row will fail hidden claims
where the customer overstates the delay or cites a superseded clause.

Per-order cap: an order may already have been refunded by an earlier claim.
The read tool `lookup_refund_history` shows how much. The host still enforces
the cap, so pass the full quote to `durability.issue_refund`, not a net amount.

Caps: stop at 8 steps. Count model calls in the Budget so cost stays comparable.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.
"""

from __future__ import annotations

from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import dispatch, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    budget = Budget()
    trace = Trace(make_run_id("single", claim_id, seed))
    proposal = 0

    def result(status: str, reason: str | None = None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn, shape="single", claim_id=claim_id, seed=seed,
            status=status, proposal_amount=proposal, budget=budget,
            trace=trace, error_reason=reason,
        )

    try:
        # This view omits parent secrets and raw headers. Ticket text never
        # overrides structured order facts or enters the trace.
        claim = dispatch(conn, budget, "get_claim_view", {"claim_id": claim_id}, worker=True)
        trace.add("claim", {"found": claim["found"]})
        if not claim["found"]:
            return result("failed", "unknown_claim")
        if not claim.get("order_id"):
            return result("needs_info", "missing_order_id")

        state: dict[str, Any] = {"order": None, "quote": None}

        def decide(observation: dict[str, Any]) -> dict[str, Any]:
            last_tool = observation.get("last_tool")
            # MockLLM returns seeded text rather than structured tool calls.
            # Keep action selection explicit and count every model call.
            complete(budget, seed=seed, purpose="plan", prompt=f"{claim_id}:{last_tool or 'start'}")
            if last_tool is None:
                action = {"tool": "lookup_order", "args": {
                    "order_id": claim["order_id"], "principal_id": claim["principal_id"],
                }}
            elif last_tool == "lookup_order":
                order_view = observation["last_result"]
                if not order_view.get("visible"):
                    trace.add("order", {"visible": False, "reason": order_view.get("reason")})
                    return {"final": {"status": "escalated", "reason": order_view.get("reason")}}
                state["order"] = order_view["order"]
                trace.add("order", {"visible": True})
                action = {"tool": "lookup_policy", "args": {}}
            elif last_tool == "lookup_policy":
                trace.add("policy", {"current_count": len(observation["last_result"]["policies"])})
                action = {"tool": "lookup_refund_history", "args": {
                    "order_id": claim["order_id"], "principal_id": claim["principal_id"],
                }}
            elif last_tool == "lookup_refund_history":
                history = observation["last_result"]
                trace.add("refund_history", {"visible": history.get("visible"),
                    "refunded_vnd": history.get("refunded_vnd", 0)})
                action = {"tool": "compute_compensation", "args": {"order": state["order"]}}
            elif last_tool == "compute_compensation":
                state["quote"] = observation["last_result"]
                trace.add("quote", {"amount_vnd": state["quote"]["amount_vnd"],
                    "reason": state["quote"]["reason"]})
                return {"final": {"status": "quoted"}}
            else:
                return {"final": {"status": "failed", "reason": "unexpected_observation"}}
            trace.add("tool_call", {"name": action["tool"]})
            return action

        loop = run_react(
            conn, budget, observation={"claim": claim}, decide=decide,
            max_steps=8, worker=True,
        )
        if loop["stopped"] == "step_cap":
            return result("failed", "step_cap")
        final = loop["final"]
        if final.get("status") == "escalated":
            return result("escalated", final.get("reason"))
        if final.get("status") != "quoted" or state["quote"] is None:
            return result("failed", "invalid_agent_result")

        proposal = int(state["quote"]["amount_vnd"])
        if proposal <= 0:
            proposal = 0
            return result("denied", state["quote"].get("reason"))

        # Pass the full quote. The host checks approval and the per-order cap.
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
        trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"]})
        if not outcome["ok"]:
            return result("failed" if outcome["conflict"] else "denied", outcome["reason"])
        return result("resolved")
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    except Exception as exc:
        # Exception text may contain customer data; report only its type.
        return result("failed", f"agent_error:{type(exc).__name__}")
    finally:
        conn.close()
