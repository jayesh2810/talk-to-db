from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd

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
) -> dict[str, Any]:
    _log(wf, f"{event_prefix}_request", "Sending prompt to stepfun-ai/step-3.5-flash", "llm")
    try:
        out = chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            debug_tag=f"{wf.workflow_id}:{event_prefix}",
        )
        _log(wf, f"{event_prefix}_success", "Received valid JSON from LLM", "llm")
        return out
    except Exception as e:
        _log(wf, f"{event_prefix}_error", f"LLM failed or JSON parse failed: {e}", "llm")
        raise


def _need_fields(obj: dict[str, Any], fields: list[str], ctx: str) -> None:
    missing = [f for f in fields if f not in obj]
    if missing:
        raise ValueError(f"{ctx}: missing fields {missing}")


def _dtype_name(dtype: Any) -> str:
    return str(dtype).lower()


def _is_pii_column(name: str) -> bool:
    n = name.lower()
    pii_tokens = (
        "name",
        "email",
        "phone",
        "address",
        "city",
        "zip",
        "postal",
        "ssn",
        "dob",
        "device",
        "ip",
    )
    return any(t in n for t in pii_tokens)


def _mask_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    s = str(v)
    if len(s) <= 2:
        return "**"
    return f"{s[:1]}***{s[-1:]}"


def _safe_table_profile(df: pd.DataFrame, table_name: str) -> dict[str, Any]:
    row_count = int(len(df))
    columns: list[dict[str, Any]] = []
    for c in df.columns:
        col = df[c]
        dtype = _dtype_name(col.dtype)
        null_pct = round(float(col.isna().mean() * 100), 2)
        unique_count = int(col.nunique(dropna=True))
        info: dict[str, Any] = {
            "column": str(c),
            "dtype": dtype,
            "null_pct": null_pct,
            "unique": unique_count,
            "pii": _is_pii_column(str(c)),
        }
        if pd.api.types.is_numeric_dtype(col) and not pd.api.types.is_bool_dtype(col):
            s = pd.to_numeric(col, errors="coerce").dropna()
            if len(s):
                info["min"] = float(s.min())
                info["p50"] = float(s.quantile(0.5))
                info["p90"] = float(s.quantile(0.9))
                info["max"] = float(s.max())
        columns.append(info)
    return {"table": table_name, "rows": row_count, "columns": columns}


def _risk_buckets_from_predictive_rows(rows: list[dict[str, Any]], score_key: str = "score") -> dict[str, Any]:
    low = 0
    med = 0
    high = 0
    for r in rows:
        try:
            s = float(r.get(score_key, 0.0))
        except (TypeError, ValueError):
            s = 0.0
        if s >= 0.75:
            high += 1
        elif s >= 0.4:
            med += 1
        else:
            low += 1
    total = low + med + high
    return {
        "total": total,
        "high": high,
        "medium": med,
        "low": low,
    }


def _masked_rows(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows[:limit]:
        masked: dict[str, Any] = {}
        for k, v in r.items():
            if _is_pii_column(str(k)):
                masked[k] = _mask_value(v)
            else:
                masked[k] = v
        out.append(masked)
    return out


def _goal_context(bundle: RFMBundle, wf: GoalWorkflow) -> dict[str, Any]:
    profile = {
        "users": _safe_table_profile(bundle.users, "users"),
        "orders": _safe_table_profile(bundle.orders, "orders"),
        "items": _safe_table_profile(bundle.items, "items"),
    }
    user_count = int(len(bundle.users))
    order_count = int(len(bundle.orders))
    item_count = int(len(bundle.items))
    orders_per_user = (float(order_count) / float(user_count)) if user_count else 0.0
    revenue_total = float(pd.to_numeric(bundle.orders.get("price"), errors="coerce").fillna(0).sum()) if "price" in bundle.orders.columns else 0.0
    return {
        "objective": wf.objective,
        "dataset_summary": {
            "users": user_count,
            "orders": order_count,
            "items": item_count,
            "orders_per_user_avg": round(orders_per_user, 3),
            "revenue_total": round(revenue_total, 2),
        },
        "schema_profile": profile,
        "privacy_mode": {
            "raw_rows_shared": False,
            "pii_policy": "name,email,phone,address,city,zip,device identifiers masked or excluded",
        },
    }


def _plan_from_llm(wf: GoalWorkflow, goal_ctx: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You are a goal-seeking analytics agent. Return STRICT JSON only. No markdown. "
        "Decide one goal_type from: churn_probability, purchase_likelihood, demand_forecast."
    )
    user = (
        f"Objective: {wf.objective}\n"
        f"Context (sanitized): {goal_ctx}\n"
        f"{SUPPORTED_HINT}\n"
        "Return JSON schema:\n"
        "{"
        '"goal_type": "...",'
        '"steps": ["...", "...", "...", "..."],'
        '"plan_rationale": "..."'
        "}"
    )
    out = _safe_json_llm(wf, "plan", system, user)
    _need_fields(out, ["goal_type", "steps", "plan_rationale"], "plan")
    out["objective"] = wf.objective
    if out.get("goal_type") not in {"churn_probability", "purchase_likelihood", "demand_forecast"}:
        raise ValueError("plan: unsupported goal_type")
    if not isinstance(out.get("steps"), list) or not out["steps"]:
        raise ValueError("plan: steps must be a non-empty list")
    return out


def _assumptions_from_llm(wf: GoalWorkflow, goal_ctx: dict[str, Any]) -> dict[str, Any]:
    system = "Return STRICT JSON only. No markdown."
    user = (
        f"Objective: {wf.objective}\nGoal type: {wf.plan.get('goal_type')}\n"
        f"Context (sanitized): {goal_ctx}\n"
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
    out = _safe_json_llm(wf, "assumptions", system, user)
    _need_fields(out, ["horizon_days", "uplift_pct", "reach_pct", "limit", "notes"], "assumptions")
    out["horizon_days"] = int(max(7, min(365, int(out.get("horizon_days", 30)))))
    out["uplift_pct"] = int(max(1, min(100, int(out.get("uplift_pct", 12)))))
    out["reach_pct"] = int(max(1, min(100, int(out.get("reach_pct", 35)))))
    out["limit"] = int(max(5, min(100, int(out.get("limit", 20)))))
    return out


def _queries_from_llm(wf: GoalWorkflow, goal_ctx: dict[str, Any]) -> dict[str, str]:
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
        f"Context (sanitized): {goal_ctx}\n"
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

    out = _safe_json_llm(wf, "queries", system, user)
    _need_fields(
        out,
        ["predictive_query", "fallback_predictive_query", "factual_query", "fallback_factual_query"],
        "queries",
    )
    for k in ["predictive_query", "fallback_predictive_query", "factual_query", "fallback_factual_query"]:
        if not isinstance(out.get(k), str) or not out[k].strip():
            raise ValueError(f"queries: invalid {k}")
    return out


def _run_with_retry(bundle: RFMBundle, primary_query: str, fallback_query: str) -> tuple[dict[str, Any], str]:
    try:
        return execute(primary_query, bundle), primary_query
    except Exception:
        return execute(fallback_query, bundle), fallback_query


def _execution_summary_from_llm(wf: GoalWorkflow, queries: dict[str, str], pred: dict[str, Any], factual: dict[str, Any], goal_ctx: dict[str, Any]) -> dict[str, Any]:
    top_pred = pred.get("results", [])[:20]
    top_fact = factual.get("results", [])[:20]
    pred_buckets = _risk_buckets_from_predictive_rows(top_pred)
    safe_pred_rows = _masked_rows(top_pred, 8)
    safe_fact_rows = _masked_rows(top_fact, 8)
    system = "Return STRICT JSON only. No markdown."
    user = (
        f"Objective: {wf.objective}\n"
        f"Goal type: {wf.plan.get('goal_type')}\n"
        f"Assumptions: {wf.assumptions}\n"
        f"Context (sanitized): {goal_ctx}\n"
        f"Predictive query: {queries.get('predictive_query')}\n"
        f"Factual query: {queries.get('factual_query')}\n"
        f"Predictive risk buckets: {pred_buckets}\n"
        f"Predictive masked sample rows: {safe_pred_rows}\n"
        f"Factual masked sample rows: {safe_fact_rows}\n"
        "Create concise execution summary with schema:\n"
        "{"
        '"avg_top_score": 0.0,'
        '"estimated_goal_movement_pct": 0.0,'
        '"insight": "...",'
        '"top_candidates": [],'
        '"supporting_rows": []'
        "}"
    )
    out = _safe_json_llm(wf, "execution_summary", system, user)
    _need_fields(out, ["avg_top_score", "estimated_goal_movement_pct", "insight", "top_candidates", "supporting_rows"], "execution_summary")
    out["predictive_query"] = queries.get("predictive_query", "")
    out["factual_query"] = queries.get("factual_query", "")
    out["risk_buckets"] = pred_buckets
    if not isinstance(out.get("top_candidates"), list):
        raise ValueError("execution_summary: top_candidates must be list")
    if not isinstance(out.get("supporting_rows"), list):
        raise ValueError("execution_summary: supporting_rows must be list")
    return out


def _actions_from_llm(wf: GoalWorkflow, goal_ctx: dict[str, Any]) -> list[dict[str, Any]]:
    system = "Return STRICT JSON only. No markdown."
    user = (
        f"Objective: {wf.objective}\n"
        f"Goal type: {wf.plan.get('goal_type')}\n"
        f"Assumptions: {wf.assumptions}\n"
        f"Context (sanitized): {goal_ctx}\n"
        f"Execution summary: {wf.execution_summary}\n"
        "Create top 3 prioritized actions.\n"
        "Schema: {\"final_actions\": [{\"priority\":1,\"action\":\"...\",\"expected_movement_pct\":1.2}]}"
    )
    out = _safe_json_llm(wf, "actions", system, user)
    _need_fields(out, ["final_actions"], "actions")
    actions = out.get("final_actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions: final_actions must be non-empty list")
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


def _start_goal(user: str, objective: str, bundle: RFMBundle) -> dict[str, Any]:
    wf = GoalWorkflow(
        workflow_id=str(uuid4())[:8],
        user=user,
        objective=objective,
    )
    _log(wf, "workflow_start", f"Objective received: {objective}")
    goal_ctx = _goal_context(bundle, wf)
    _log(wf, "privacy_context_built", "Using schema+aggregates+risk buckets; raw PII rows are blocked")
    try:
        plan = _plan_from_llm(wf, goal_ctx)
        wf.plan = plan
        wf.assumptions = _assumptions_from_llm(wf, goal_ctx)
        _log(wf, "workflow_initialized", f"Goal type selected: {wf.plan.get('goal_type')}")
    except Exception as e:
        wf.execution_summary = {
            "status": "needs_user_input",
            "detail": f"Agent could not initialize plan/assumptions: {e}",
        }
        _log(wf, "workflow_init_failed", str(e))
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
    goal_ctx = _goal_context(bundle, wf)

    if wf.stage == "draft_plan":
        wf.stage = "assumptions"
        wf.pending_approval = "assumptions"
        _log(wf, "stage_transition", "Moved to assumptions checkpoint")
        return _agent_payload(
            wf,
            "Checkpoint B: Review assumptions. Approve to execute, or revise with `/goal revise <workflow_id> uplift 15 reach 40 45 days`.",
        )

    if wf.stage == "assumptions":
        queries = _queries_from_llm(wf, goal_ctx)
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
            wf.execution_summary = _execution_summary_from_llm(wf, queries, pred, factual, goal_ctx)
            wf.final_actions = _actions_from_llm(wf, goal_ctx)
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


def _revise_goal(user: str, workflow_id: str | None, revision: str, bundle: RFMBundle) -> dict[str, Any]:
    wf = WORKFLOWS.get(user)
    if wf is None:
        return {"mode": "agent_goal", "summary": "No active workflow found to revise. Start with `/goal <objective>`.", "query_type": "agent_goal"}
    if workflow_id and wf.workflow_id != workflow_id:
        return {"mode": "agent_goal", "summary": f"Workflow id mismatch. Active workflow is `{wf.workflow_id}`.", "query_type": "agent_goal"}
    _log(wf, "revise_received", f"Stage={wf.stage}; revision={revision}")
    goal_ctx = _goal_context(bundle, wf)

    system = "Return STRICT JSON only. No markdown."
    user_prompt = (
        f"Current stage: {wf.stage}\n"
        f"Objective: {wf.objective}\n"
        f"Current plan: {wf.plan}\n"
        f"Current assumptions: {wf.assumptions}\n"
        f"Context (sanitized): {goal_ctx}\n"
        f"Revision request: {revision}\n"
        "Return schema:\n"
        "{"
        '"updated_plan": {...},'
        '"updated_assumptions": {...},'
        '"revision_note": "..."'
        "}"
    )
    out = _safe_json_llm(wf, "revise", system, user_prompt)
    _need_fields(out, ["updated_plan", "updated_assumptions", "revision_note"], "revise")

    if isinstance(out.get("updated_plan"), dict):
        wf.plan = {**wf.plan, **out["updated_plan"]}
    if isinstance(out.get("updated_assumptions"), dict):
        wf.assumptions = {**wf.assumptions, **out["updated_assumptions"]}
    wf.assumptions["revision_note"] = out.get("revision_note", revision.strip())
    _log(wf, "revise_applied", "Revision changes merged into workflow state")

    if wf.stage == "final_actions":
        wf.final_actions = _actions_from_llm(wf, goal_ctx)
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
        return _revise_goal(user, wf_id, revision, bundle)

    objective = raw[len("/goal") :].strip()
    if not objective:
        return {
            "mode": "agent_goal",
            "summary": "Please provide an objective. Example: `/goal reduce churn by 10% in 30 days`.",
            "query_type": "agent_goal",
        }
    return _start_goal(user, objective, bundle)
