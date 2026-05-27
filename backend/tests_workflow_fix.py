"""
Tests for the /goal workflow fixes:
  1. Workflows keyed by workflow_id (multi-workflow per user, lookup by id).
  2. Planning failure → "failed" stage, no zombie "Review the plan".
  3. needs_clarification → "awaiting_clarification" stage; revise re-plans.
  4. result_summarize dropped silently from incoming plans.
  5. Forbidden-phrase guard uses word boundaries ("rocket" allowed, "auc" blocked).

Plus the main.py webhook SSRF allow-list.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rfm.cache import RFMBundle  # noqa: E402
from agent import workflow as wf_mod  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((PASS if cond else FAIL, name, detail))
    marker = "+" if cond else "X"
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail and not cond else ""))


def _synthetic_bundle() -> RFMBundle:
    users = pd.DataFrame({
        "user_id": [1, 2, 3, 4],
        "age": [25, 42, 31, 67],
        "active": [True, False, True, True],
    })
    items = pd.DataFrame({
        "item_id": [10, 11, 12, 13],
        "item_name": ["Jeans", "Tee", "Hat", "Boots"],
        "category": ["Trousers", "Tops", "Hats", "Trousers"],
    })
    orders = pd.DataFrame({
        "order_id": [100, 101, 102, 103, 104],
        "user_id": [1, 1, 2, 3, 4],
        "item_id": [10, 11, 12, 13, 10],
        "price": [80.0, 25.0, 15.0, 120.0, 80.0],
        "date": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01", "2026-03-15", "2026-04-01"]),
    })
    return RFMBundle(graph=None, model=None, users=users, items=items, orders=orders)


def _reset() -> None:
    wf_mod.WORKFLOWS.clear()
    wf_mod.LAST_BY_USER.clear()


class _Stubber:
    """Override functions in agent.workflow for one test, then restore."""

    def __init__(self) -> None:
        self.saved: dict[str, Any] = {}

    def patch(self, name: str, value: Any) -> None:
        self.saved[name] = getattr(wf_mod, name)
        setattr(wf_mod, name, value)

    def restore(self) -> None:
        for k, v in self.saved.items():
            setattr(wf_mod, k, v)
        self.saved.clear()


VALID_PLAN: dict[str, Any] = {
    "goal_type": "churn_probability",
    "objective": "...",
    "needs_clarification": False,
    "clarifying_questions": [],
    "plan_rationale": "Score users and act on highest risk.",
    "success_metric": "Churn reduced 2pct.",
    "steps": ["Inspect schema", "Predict churn", "Act on top risk"],
    "tool_steps": [
        {"step": 1, "tool": "schema_inspect", "purpose": "schema", "query": ""},
        {"step": 2, "tool": "predict_execute", "purpose": "churn",
         "query": "PREDICT churn_probability FOR EACH customer USING orders HORIZON 60 days RETURN score LIMIT 20"},
        {"step": 3, "tool": "match_execute", "purpose": "look up active",
         "query": "MATCH customer WHERE active = true RETURN user_id LIMIT 20"},
    ],
}


# ─── 1. Workflows keyed by workflow_id ──────────────────────────────────

def test_workflow_id_lookup() -> None:
    print("\n[1] workflow_id-based lookup")
    _reset()
    stub = _Stubber()
    plan_responses = iter([VALID_PLAN, VALID_PLAN])
    stub.patch("_plan_from_llm", lambda wf, ctx: next(plan_responses))
    bundle = _synthetic_bundle()
    try:
        out1 = wf_mod._start_goal("alice", "reduce churn", bundle)
        wf1 = out1["workflow_id"]
        out2 = wf_mod._start_goal("alice", "grow purchases", bundle)
        wf2 = out2["workflow_id"]

        check("two start_goal calls produce different ids", wf1 != wf2)
        check("both workflows still resolvable by id",
              wf_mod._get_workflow("alice", wf1) is not None
              and wf_mod._get_workflow("alice", wf2) is not None)
        check("LAST_BY_USER points to most recent",
              wf_mod.LAST_BY_USER["alice"] == wf2)
        check("default lookup (no id) returns most recent",
              wf_mod._get_workflow("alice", None).workflow_id == wf2)

        # Cross-user isolation: bob cannot read alice's workflow even with id
        check("cross-user id access blocked",
              wf_mod._get_workflow("bob", wf1) is None)
    finally:
        stub.restore()


# ─── 2. Planning failure → "failed" stage ───────────────────────────────

def test_planning_failure_no_zombie() -> None:
    print("\n[2] planning failure does not leave a zombie checkpoint")
    _reset()
    stub = _Stubber()

    def boom(wf, ctx):
        raise RuntimeError("LLM exploded")

    stub.patch("_plan_from_llm", boom)
    bundle = _synthetic_bundle()
    try:
        out = wf_mod._start_goal("alice", "vague goal", bundle)
        check("stage is 'failed' (not draft_plan)", out["stage"] == "failed",
              repr(out["stage"]))
        check("pending_approval is None", out["pending_approval"] is None)
        check("summary mentions failure, not 'Review the Kumo-first plan'",
              "Review" not in out["summary"] and "couldn't draft" in out["summary"].lower(),
              repr(out["summary"]))

        # Approving the failed workflow does NOT execute anything
        wf_id = out["workflow_id"]
        out_a = wf_mod._approve_goal("alice", bundle, wf_id)
        check("approve on failed workflow is rejected cleanly",
              "failed" in out_a["summary"].lower(), repr(out_a["summary"]))
    finally:
        stub.restore()


# ─── 3. Clarification path ──────────────────────────────────────────────

def test_clarification_flow() -> None:
    print("\n[3] needs_clarification is surfaced and resolves on revise")
    _reset()
    stub = _Stubber()
    # First plan call → clarification; after revise → valid plan.
    call_log: list[str] = []

    def staged(wf, ctx):
        call_log.append(wf.objective)
        if "Clarification" not in wf.objective:
            return {"_needs_clarification": True,
                    "clarifying_questions": ["What is the time horizon?",
                                             "Which customer segment?"]}
        return VALID_PLAN

    stub.patch("_plan_from_llm", staged)
    bundle = _synthetic_bundle()
    try:
        out1 = wf_mod._start_goal("alice", "do something about customers", bundle)
        check("stage is awaiting_clarification",
              out1["stage"] == "awaiting_clarification", repr(out1["stage"]))
        check("proposal carries clarifying_questions",
              out1["proposal"]["clarifying_questions"]
              == ["What is the time horizon?", "Which customer segment?"],
              repr(out1["proposal"]))
        check("summary surfaces the questions",
              "horizon" in out1["summary"].lower(), repr(out1["summary"]))

        # Now revise with the answer → re-plans into draft_plan
        out2 = wf_mod._revise_goal("alice", out1["workflow_id"],
                                   "60 days, active customers", bundle)
        check("after revise: stage is draft_plan",
              out2["stage"] == "draft_plan", repr(out2["stage"]))
        check("after revise: proposal contains a plan",
              out2["proposal"] and out2["proposal"].get("plan", {}).get("tool_steps"),
              repr(out2.get("proposal")))
        check("planner re-invoked with appended clarification",
              "[Clarification: 60 days, active customers]" in call_log[-1])

        # Approving while in clarification stage is rejected
        _reset()
        wf_mod.WORKFLOWS.clear()
        wf_mod.LAST_BY_USER.clear()
        out_c = wf_mod._start_goal("bob", "vague goal 2", bundle)
        wid = out_c["workflow_id"]
        out_d = wf_mod._approve_goal("bob", bundle, wid)
        check("approve while awaiting_clarification is rejected",
              "clarification" in out_d["summary"].lower(),
              repr(out_d["summary"]))
    finally:
        stub.restore()


# ─── 4. result_summarize placebo removed ────────────────────────────────

def test_result_summarize_stripped() -> None:
    print("\n[4] result_summarize step is dropped by _normalize_plan")
    raw = {
        "goal_type": "churn_probability",
        "plan_rationale": "Test.",
        "steps": ["a", "b"],
        "tool_steps": [
            {"step": 1, "tool": "schema_inspect", "purpose": "", "query": ""},
            {"step": 2, "tool": "predict_execute", "purpose": "",
             "query": "PREDICT churn_probability FOR EACH customer HORIZON 30 days LIMIT 5"},
            {"step": 3, "tool": "result_summarize", "purpose": "", "query": ""},
        ],
    }
    plan = wf_mod._normalize_plan(raw, "obj")
    tools_kept = [s["tool"] for s in plan["tool_steps"]]
    check("result_summarize stripped",
          "result_summarize" not in tools_kept, repr(tools_kept))
    check("real tools preserved",
          tools_kept == ["schema_inspect", "predict_execute"], repr(tools_kept))

    # If the plan was ONLY result_summarize, normalization rejects (no real work)
    raw2 = {
        "goal_type": "churn_probability",
        "plan_rationale": "Test.",
        "steps": ["a"],
        "tool_steps": [
            {"step": 1, "tool": "result_summarize", "purpose": "", "query": ""},
        ],
    }
    raised = False
    try:
        wf_mod._normalize_plan(raw2, "obj")
    except ValueError:
        raised = True
    check("plan with only placebo step is rejected", raised)

    # ALLOWED_TOOLS no longer advertises result_summarize
    check("ALLOWED_TOOLS does not include result_summarize",
          "result_summarize" not in wf_mod.ALLOWED_TOOLS,
          repr(wf_mod.ALLOWED_TOOLS))


# ─── 5. Forbidden-phrase word-boundary check ────────────────────────────

def test_forbidden_phrases_word_boundary() -> None:
    print("\n[5] forbidden phrases use word boundaries")
    bad_plan = {
        "goal_type": "churn_probability",
        "plan_rationale": "We will engineer features for users.",
        "steps": ["feature engineering pass"],
        "tool_steps": [
            {"step": 1, "tool": "schema_inspect", "purpose": "", "query": ""},
        ],
    }
    raised = False
    msg = ""
    try:
        wf_mod._normalize_plan(bad_plan, "obj")
    except ValueError as e:
        raised = True
        msg = str(e)
    check("'feature engineering' still blocked", raised and "feature engineering" in msg,
          msg)

    # 'rocket' must not trigger 'roc'; 'caucus' must not trigger 'auc'
    ok_plan_text = "Plan to drive rocket-ship growth across our caucus of customers."
    check("'rocket-ship' does NOT trigger 'roc'",
          wf_mod._forbidden_hit(ok_plan_text) is None,
          repr(wf_mod._forbidden_hit(ok_plan_text)))

    check("standalone 'auc' still blocked",
          wf_mod._forbidden_hit("we should optimize auc here") == "auc")
    check("standalone 'roc' still blocked",
          wf_mod._forbidden_hit("compute the roc curve") == "roc")


# ─── 6. Webhook SSRF validation ─────────────────────────────────────────

def test_webhook_validation() -> None:
    print("\n[6] webhook URL validation (SSRF allow-list)")
    # Import only when needed because main.py runs `from llm.claude import get_client`
    # at import time, which fails without ANTHROPIC_API_KEY. So set a dummy.
    os.environ.setdefault("ANTHROPIC_API_KEY", "test")
    from main import _validate_webhook_url
    from fastapi import HTTPException

    def expect(url: str, status: int, env: str | None) -> None:
        prev = os.environ.get("WEBHOOK_ALLOWED_HOSTS")
        if env is None:
            os.environ.pop("WEBHOOK_ALLOWED_HOSTS", None)
        else:
            os.environ["WEBHOOK_ALLOWED_HOSTS"] = env
        ok = False
        actual: str | int | None = None
        try:
            _validate_webhook_url(url)
            ok = (status == 0)
            actual = "ok"
        except HTTPException as e:
            ok = (e.status_code == status)
            actual = e.status_code
        finally:
            if prev is None:
                os.environ.pop("WEBHOOK_ALLOWED_HOSTS", None)
            else:
                os.environ["WEBHOOK_ALLOWED_HOSTS"] = prev
        check(f"webhook {url!r} env={env!r} -> {status}", ok,
              f"got {actual}")

    expect("http://hooks.slack.com/path", 0, "hooks.slack.com")
    expect("https://hooks.slack.com/path", 0, "hooks.slack.com,api.foo.com")
    expect("http://hooks.slack.com/path", 403, None)              # no env → disabled
    expect("http://evil.example.com/path", 403, "hooks.slack.com") # not allowed
    expect("http://127.0.0.1:8080/admin", 403, "hooks.slack.com,127.0.0.1")  # loopback blocked
    expect("http://10.0.0.5/", 403, "hooks.slack.com,10.0.0.5")   # private IP blocked
    expect("file:///etc/passwd", 400, "hooks.slack.com")          # wrong scheme
    expect("http:///nohost", 400, "hooks.slack.com")              # no host
    expect("http://169.254.169.254/latest/meta-data/", 403,
           "hooks.slack.com,169.254.169.254")                      # link-local (cloud metadata)


# ─── 7. Approve → execute path with mocked tools/LLM ────────────────────

def test_approve_execute_path() -> None:
    print("\n[7] approve drives execute → final_actions stage")
    _reset()
    stub = _Stubber()

    stub.patch("_plan_from_llm", lambda wf, ctx: VALID_PLAN)

    def fake_run_plan_tools(wf, bundle):
        return {
            "status": "executed",
            "avg_top_score": 0.6,
            "estimated_goal_movement_pct": None,
            "risk_buckets": {"total": 4, "high": 1, "medium": 2, "low": 1},
            "top_candidates": [{"user_id": 1, "score": 0.9}],
            "supporting_rows": [],
            "tool_results": [],
            "used_queries": [],
            "privacy_note": "stubbed",
        }

    stub.patch("_run_plan_tools", fake_run_plan_tools)
    stub.patch("_actions_from_llm",
               lambda wf: [{"priority": 1, "action": "outreach",
                            "target_group": "high", "reason": "high churn",
                            "expected_movement_pct": None}])

    bundle = _synthetic_bundle()
    try:
        out1 = wf_mod._start_goal("alice", "reduce churn", bundle)
        check("start_goal: stage=draft_plan", out1["stage"] == "draft_plan")
        wid = out1["workflow_id"]

        out2 = wf_mod._approve_goal("alice", bundle, wid)
        check("approve: stage=final_actions",
              out2["stage"] == "final_actions", repr(out2["stage"]))
        check("approve: final_actions present",
              out2["proposal"]["final_actions"][0]["action"] == "outreach")

        # Second approve finalizes
        out3 = wf_mod._approve_goal("alice", bundle, wid)
        check("second approve: stage=completed", out3["stage"] == "completed")
    finally:
        stub.restore()


# ─── Run ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_workflow_id_lookup()
    test_planning_failure_no_zombie()
    test_clarification_flow()
    test_result_summarize_stripped()
    test_forbidden_phrases_word_boundary()
    test_webhook_validation()
    test_approve_execute_path()

    fails = [r for r in results if r[0] == FAIL]
    passes = [r for r in results if r[0] == PASS]
    print(f"\nSummary: {len(passes)} passed, {len(fails)} failed (total {len(results)})")
    if fails:
        for _, name, detail in fails:
            print(f"  FAIL: {name}  -- {detail}")
        sys.exit(1)
    sys.exit(0)
