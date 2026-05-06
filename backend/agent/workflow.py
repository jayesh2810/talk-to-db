from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from llm.nvidia_agent import chat_json
from pql.executor import execute
from rfm.cache import RFMBundle


@dataclass
class GoalWorkflow:
    workflow_id: str
    user: str
    objective: str
    stage: str = "draft_plan"
    pending_approval: str | None = "plan"
    plan: dict[str, Any] = field(default_factory=dict)
    assumptions: dict[str, Any] = field(default_factory=dict)
    execution_summary: dict[str, Any] = field(default_factory=dict)
    final_actions: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)


WORKFLOWS: dict[str, GoalWorkflow] = {}


SUPPORTED_HINT = (
    "Supported predictive goals in this app: churn_probability, purchase_likelihood, demand_forecast."
)


def _log(wf: GoalWorkflow, event: str, detail: str, source: str = "agent") -> None:
    row = {
        "time": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "event": event,
        "detail": detail,
    }
    wf.logs.append(row)
    print(f"[goal-agent][{wf.workflow_id}][{event}] {detail}")


def _safe_json_llm(
    wf: GoalWorkflow,
    event_prefix: str,
    system_prompt: str,
    user_prompt: str,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    _log(wf, f"{event_prefix}_request", "Sending prompt to stepfun-ai/step-3.5-flash", "llm")
    try:
        out = chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
        )
        _log(wf, f"{event_prefix}_success", "Received valid JSON from LLM", "llm")
        return out
    except Exception:
        _log(wf, f"{event_prefix}_fallback", "LLM failed or JSON parse failed; fallback applied", "llm")
        return fallback


def _plan_from_llm(wf: GoalWorkflow) -> dict[str, Any]:
    system = (
        "You are a goal-seeking analytics agent. Return STRICT JSON only. No markdown. "
        "Decide one goal_type from: churn_probability, purchase_likelihood, demand_forecast."
    )
    user = (
        f"Objective: {wf.objective}\n"
        f"{SUPPORTED_HINT}\n"
        "Return JSON schema:\n"
        "{"
        '"goal_type": "...",'
        '"steps": ["...", "...", "...", "..."],'
        '"plan_rationale": "..."'
        "}"
    )
    fallback = {
        "goal_type": "churn_probability",
        "steps": [
            "Identify highest-impact entities with predictive scoring.",
            "Break down likely impact drivers from available profile fields.",
            "Estimate achievable movement using assumptions.",
            "Propose prioritized actions with expected impact.",
        ],
        "plan_rationale": "Fallback plan used due to model response parsing failure.",
    }
    out = _safe_json_llm(wf, "plan", system, user, fallback)
    out["objective"] = wf.objective
    if out.get("goal_type") not in {"churn_probability", "purchase_likelihood", "demand_forecast"}:
        out["goal_type"] = "churn_probability"
    if not isinstance(out.get("steps"), list) or not out["steps"]:
        out["steps"] = fallback["steps"]
    return out


def _assumptions_from_llm(wf: GoalWorkflow) -> dict[str, Any]:
    system = "Return STRICT JSON only. No markdown."
    user = (
        f"Objective: {wf.objective}\nGoal type: {wf.plan.get('goal_type')}\n"
        "Provide practical assumptions for this demo app.\n"
        "Schema:\n"
        "{"
        '"horizon_days": 30,'
        '"uplift_pct": 12,'
        '"reach_pct": 35,'
        '"limit": 20,'
        '"notes": "..."'
        "}"
    )
    fallback = {"horizon_days": 30, "uplift_pct": 12, "reach_pct": 35, "limit": 20, "notes": "Fallback assumptions."}
    out = _safe_json_llm(wf, "assumptions", system, user, fallback)
    out["horizon_days"] = int(max(7, min(365, int(out.get("horizon_days", 30)))))
    out["uplift_pct"] = int(max(1, min(100, int(out.get("uplift_pct", 12)))))
    out["reach_pct"] = int(max(1, min(100, int(out.get("reach_pct", 35)))))
    out["limit"] = int(max(5, min(100, int(out.get("limit", 20)))))
    return out


def _queries_from_llm(wf: GoalWorkflow) -> dict[str, str]:
    system = (
        "Return STRICT JSON only. No markdown. "
        "Generate app-compatible PQL strings for this backend parser. "
        "Predictive queries must use: PREDICT <type> FOR EACH <entity> USING ... HORIZON N days RETURN ... ORDER BY ... LIMIT ... "
        "Factual query must use MATCH."
    )
    user = (
        f"Objective: {wf.objective}\n"
        f"Goal type: {wf.plan.get('goal_type')}\n"
        f"Assumptions: {wf.assumptions}\n"
        "Schema:\n"
        "{"
        '"predictive_query": "...",'
        '"fallback_predictive_query": "...",'
        '"factual_query": "...",'
        '"fallback_factual_query": "..."'
        "}"
    )
    gt = wf.plan.get("goal_type", "churn_probability")
    h = wf.assumptions.get("horizon_days", 30)
    l = wf.assumptions.get("limit", 20)
    if gt == "purchase_likelihood":
        pred = f"PREDICT purchase_likelihood FOR EACH customer USING orders, items HORIZON {h} days RETURN score ORDER BY score DESC LIMIT {l}"
        fallback_pred = "PREDICT purchase_likelihood FOR EACH customer USING orders, items HORIZON 30 days RETURN score ORDER BY score DESC LIMIT 15"
    elif gt == "demand_forecast":
        pred = f"PREDICT demand_forecast FOR EACH product USING orders, items HORIZON {h} days RETURN category, score, predicted_revenue ORDER BY score DESC LIMIT {l}"
        fallback_pred = "PREDICT demand_forecast FOR EACH product USING orders, items HORIZON 30 days RETURN category, score, predicted_revenue ORDER BY score DESC LIMIT 15"
    else:
        pred = f"PREDICT churn_probability FOR EACH customer USING orders HORIZON {h} days RETURN score ORDER BY score DESC LIMIT {l}"
        fallback_pred = "PREDICT churn_probability FOR EACH customer USING orders HORIZON 30 days RETURN score ORDER BY score DESC LIMIT 15"

    fallback = {
        "predictive_query": pred,
        "fallback_predictive_query": fallback_pred,
        "factual_query": "MATCH users RETURN user_id, active, age LIMIT 20",
        "fallback_factual_query": "MATCH users RETURN user_id, active, age LIMIT 10",
    }
    out = _safe_json_llm(wf, "queries", system, user, fallback)
    for k in fallback:
        if not isinstance(out.get(k), str) or not out[k].strip():
            out[k] = fallback[k]
    return out


def _run_with_retry(bundle: RFMBundle, primary_query: str, fallback_query: str) -> tuple[dict[str, Any], str]:
    try:
        return execute(primary_query, bundle), primary_query
    except Exception:
        return execute(fallback_query, bundle), fallback_query


def _execution_summary_from_llm(wf: GoalWorkflow, queries: dict[str, str], pred: dict[str, Any], factual: dict[str, Any]) -> dict[str, Any]:
    top_pred = pred.get("results", [])[:10]
    top_fact = factual.get("results", [])[:10]
    system = "Return STRICT JSON only. No markdown."
    user = (
        f"Objective: {wf.objective}\n"
        f"Goal type: {wf.plan.get('goal_type')}\n"
        f"Assumptions: {wf.assumptions}\n"
        f"Predictive query: {queries.get('predictive_query')}\n"
        f"Factual query: {queries.get('factual_query')}\n"
        f"Predictive results sample: {top_pred}\n"
        f"Factual results sample: {top_fact}\n"
        "Create concise execution summary with schema:\n"
        "{"
        '"avg_top_score": 0.0,'
        '"estimated_goal_movement_pct": 0.0,'
        '"insight": "...",'
        '"top_candidates": [],'
        '"supporting_rows": []'
        "}"
    )
    fallback = {
        "avg_top_score": 0.0,
        "estimated_goal_movement_pct": 0.0,
        "insight": "Fallback summary generated.",
        "top_candidates": top_pred[:5],
        "supporting_rows": top_fact[:5],
    }
    out = _safe_json_llm(wf, "execution_summary", system, user, fallback)
    out["predictive_query"] = queries.get("predictive_query", "")
    out["factual_query"] = queries.get("factual_query", "")
    if not isinstance(out.get("top_candidates"), list):
        out["top_candidates"] = top_pred[:5]
    if not isinstance(out.get("supporting_rows"), list):
        out["supporting_rows"] = top_fact[:5]
    return out


def _actions_from_llm(wf: GoalWorkflow) -> list[dict[str, Any]]:
    system = "Return STRICT JSON only. No markdown."
    user = (
        f"Objective: {wf.objective}\n"
        f"Goal type: {wf.plan.get('goal_type')}\n"
        f"Assumptions: {wf.assumptions}\n"
        f"Execution summary: {wf.execution_summary}\n"
        "Create top 3 prioritized actions.\n"
        "Schema: {\"final_actions\": [{\"priority\":1,\"action\":\"...\",\"expected_movement_pct\":1.2}]}"
    )
    fallback = {
        "final_actions": [
            {"priority": 1, "action": "Target top-scored cohort first with personalized outreach.", "expected_movement_pct": 1.5},
            {"priority": 2, "action": "Apply medium-touch campaign to mid-risk cohort.", "expected_movement_pct": 0.9},
            {"priority": 3, "action": "Re-rank and monitor weekly for iterative optimization.", "expected_movement_pct": 0.6},
        ]
    }
    out = _safe_json_llm(wf, "actions", system, user, fallback)
    actions = out.get("final_actions", fallback["final_actions"])
    if not isinstance(actions, list) or not actions:
        actions = fallback["final_actions"]
    return actions[:5]


def _agent_payload(wf: GoalWorkflow, summary: str) -> dict[str, Any]:
    proposal: dict[str, Any] | None = None
    if wf.stage == "draft_plan":
        proposal = {"plan": wf.plan}
    elif wf.stage == "assumptions":
        proposal = {"assumptions": wf.assumptions}
    elif wf.stage == "final_actions":
        proposal = {"final_actions": wf.final_actions}
    return {
        "mode": "agent_goal",
        "summary": summary,
        "workflow_id": wf.workflow_id,
        "stage": wf.stage,
        "pending_approval": wf.pending_approval,
        "proposal": proposal,
        "execution_summary": wf.execution_summary or None,
        "agent_logs": wf.logs[-60:],
        "query_type": "agent_goal",
    }


def _start_goal(user: str, objective: str) -> dict[str, Any]:
    wf = GoalWorkflow(
        workflow_id=str(uuid4())[:8],
        user=user,
        objective=objective,
    )
    _log(wf, "workflow_start", f"Objective received: {objective}")
    plan = _plan_from_llm(wf)
    wf.plan = plan
    wf.assumptions = _assumptions_from_llm(wf)
    _log(wf, "workflow_initialized", f"Goal type selected: {wf.plan.get('goal_type')}")
    WORKFLOWS[user] = wf
    return _agent_payload(
        wf,
        "Checkpoint A: Review plan. Approve to continue, or revise with `/goal revise <workflow_id> <changes>`.",
    )


def _approve_goal(user: str, bundle: RFMBundle, workflow_id: str | None) -> dict[str, Any]:
    wf = WORKFLOWS.get(user)
    if wf is None:
        return {"mode": "agent_goal", "summary": "No active workflow found. Start with `/goal <objective>`.", "query_type": "agent_goal"}
    if workflow_id and wf.workflow_id != workflow_id:
        return {"mode": "agent_goal", "summary": f"Workflow id mismatch. Active workflow is `{wf.workflow_id}`.", "query_type": "agent_goal"}
    _log(wf, "approve_received", f"Stage={wf.stage}")

    if wf.stage == "draft_plan":
        wf.stage = "assumptions"
        wf.pending_approval = "assumptions"
        _log(wf, "stage_transition", "Moved to assumptions checkpoint")
        return _agent_payload(
            wf,
            "Checkpoint B: Review assumptions. Approve to execute, or revise with `/goal revise <workflow_id> uplift 15 reach 40 45 days`.",
        )

    if wf.stage == "assumptions":
        queries = _queries_from_llm(wf)
        try:
            _log(wf, "execute_predictive_attempt", queries["predictive_query"])
            pred, used_pred = _run_with_retry(bundle, queries["predictive_query"], queries["fallback_predictive_query"])
            if used_pred != queries["predictive_query"]:
                _log(wf, "execute_predictive_retry", "Primary predictive query failed; fallback used")
            _log(wf, "execute_factual_attempt", queries["factual_query"])
            factual, used_factual = _run_with_retry(bundle, queries["factual_query"], queries["fallback_factual_query"])
            if used_factual != queries["factual_query"]:
                _log(wf, "execute_factual_retry", "Primary factual query failed; fallback used")
            queries["predictive_query"] = used_pred
            queries["factual_query"] = used_factual
            wf.execution_summary = _execution_summary_from_llm(wf, queries, pred, factual)
            wf.final_actions = _actions_from_llm(wf)
            wf.stage = "final_actions"
            wf.pending_approval = "final_actions"
            _log(wf, "stage_transition", "Moved to final_actions checkpoint")
            return _agent_payload(
                wf,
                "Checkpoint C: Review final actions and expected movement. Approve to finalize, or revise with `/goal revise <workflow_id> ...`.",
            )
        except Exception:
            _log(wf, "execution_failed", "Execution failed after retry; needs user input")
            wf.execution_summary = {
                "status": "needs_user_input",
                "detail": "Execution failed after retry. Please revise objective/assumptions and approve again.",
            }
            return _agent_payload(
                wf,
                "Execution failed after retry and needs clarification. Revise assumptions and approve again.",
            )

    if wf.stage == "final_actions":
        wf.stage = "completed"
        wf.pending_approval = None
        _log(wf, "workflow_completed", "Final approval received; workflow closed")
        return _agent_payload(wf, "Workflow finalized. Start a new one with `/goal <objective>`.")

    return _agent_payload(wf, "Workflow already completed.")


def _revise_goal(user: str, workflow_id: str | None, revision: str) -> dict[str, Any]:
    wf = WORKFLOWS.get(user)
    if wf is None:
        return {"mode": "agent_goal", "summary": "No active workflow found to revise. Start with `/goal <objective>`.", "query_type": "agent_goal"}
    if workflow_id and wf.workflow_id != workflow_id:
        return {"mode": "agent_goal", "summary": f"Workflow id mismatch. Active workflow is `{wf.workflow_id}`.", "query_type": "agent_goal"}
    _log(wf, "revise_received", f"Stage={wf.stage}; revision={revision}")

    system = "Return STRICT JSON only. No markdown."
    user_prompt = (
        f"Current stage: {wf.stage}\n"
        f"Objective: {wf.objective}\n"
        f"Current plan: {wf.plan}\n"
        f"Current assumptions: {wf.assumptions}\n"
        f"Revision request: {revision}\n"
        "Return schema:\n"
        "{"
        '"updated_plan": {...},'
        '"updated_assumptions": {...},'
        '"revision_note": "..."'
        "}"
    )
    fallback = {
        "updated_plan": wf.plan,
        "updated_assumptions": wf.assumptions,
        "revision_note": revision.strip(),
    }
    out = _safe_json_llm(wf, "revise", system, user_prompt, fallback)

    if isinstance(out.get("updated_plan"), dict):
        wf.plan = {**wf.plan, **out["updated_plan"]}
    if isinstance(out.get("updated_assumptions"), dict):
        wf.assumptions = {**wf.assumptions, **out["updated_assumptions"]}
    wf.assumptions["revision_note"] = out.get("revision_note", revision.strip())
    _log(wf, "revise_applied", "Revision changes merged into workflow state")

    if wf.stage == "final_actions":
        wf.final_actions = _actions_from_llm(wf)
        return _agent_payload(wf, "Final actions updated based on your revision. Approve to finalize.")
    if wf.stage == "assumptions":
        return _agent_payload(wf, "Assumptions updated. Approve to execute with revised values.")
    return _agent_payload(wf, "Draft plan updated. Approve when ready.")


def handle_goal_message(user: str, message: str, bundle: RFMBundle) -> dict[str, Any] | None:
    raw = message.strip()
    if not raw.lower().startswith("/goal"):
        return None

    parts = raw.split(maxsplit=3)
    if len(parts) == 1:
        return {
            "mode": "agent_goal",
            "summary": "Usage: `/goal <objective>` or `/goal approve <workflow_id>` or `/goal revise <workflow_id> <changes>`",
            "query_type": "agent_goal",
        }

    cmd = parts[1].lower()
    if cmd == "approve":
        wf_id = parts[2] if len(parts) >= 3 else None
        return _approve_goal(user, bundle, wf_id)

    if cmd == "revise":
        wf_id = parts[2] if len(parts) >= 3 else None
        revision = parts[3] if len(parts) >= 4 else ""
        if not revision:
            return {
                "mode": "agent_goal",
                "summary": "Please provide revision text after workflow id, e.g. `/goal revise 1234abcd uplift 15 reach 40`.",
                "query_type": "agent_goal",
            }
        return _revise_goal(user, wf_id, revision)

    objective = raw[len("/goal") :].strip()
    if not objective:
        return {
            "mode": "agent_goal",
            "summary": "Please provide an objective. Example: `/goal reduce churn by 10% in 30 days`.",
            "query_type": "agent_goal",
        }
    return _start_goal(user, objective)
