from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import time
from typing import Any
from uuid import uuid4

import pandas as pd

from llm.claude import chat_json
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
    execution_summary: dict[str, Any] = field(default_factory=dict)
    final_actions: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)


WORKFLOWS: dict[str, GoalWorkflow] = {}

SUPPORTED_GOALS = {"churn_probability", "purchase_likelihood", "demand_forecast"}
ALLOWED_TOOLS = {"schema_inspect", "predict_execute", "match_execute", "result_summarize"}
FORBIDDEN_PLAN_PHRASES = (
    "feature engineering",
    "engineer features",
    "manual features",
    "train model",
    "training model",
    "cross-validation",
    "cross validation",
    "auc",
    "roc",
    "classification algorithm",
    "regression algorithm",
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
    *,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    prompt_chars = len(system_prompt) + len(user_prompt)
    _log(wf, f"{event_prefix}_request", f"Sending prompt to Anthropic Claude ({prompt_chars:,} chars)", "llm")
    started = time.perf_counter()
    try:
        out = chat_json(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            debug_tag=f"{wf.workflow_id}:{event_prefix}",
        )
        elapsed = round(time.perf_counter() - started, 2)
        _log(wf, f"{event_prefix}_success", f"Received valid JSON from LLM in {elapsed}s", "llm")
        return out
    except Exception as e:
        _log(wf, f"{event_prefix}_error", f"LLM failed or JSON parse failed: {e}", "llm")
        raise


def _need_fields(obj: dict[str, Any], fields: list[str], ctx: str) -> None:
    missing = [f for f in fields if f not in obj]
    if missing:
        raise ValueError(f"{ctx}: missing fields {missing}")


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
        "vin",
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
        info: dict[str, Any] = {
            "column": str(c),
            "dtype": str(col.dtype).lower(),
            "pii": _is_pii_column(str(c)),
        }
        null_pct = round(float(col.isna().mean() * 100), 1)
        if null_pct:
            info["null_pct"] = null_pct
        columns.append(info)
    return {"table": table_name, "rows": row_count, "columns": columns}


def _goal_context(bundle: RFMBundle, wf: GoalWorkflow) -> dict[str, Any]:
    user_count = int(len(bundle.users))
    order_count = int(len(bundle.orders))
    item_count = int(len(bundle.items))
    orders_per_user = (float(order_count) / float(user_count)) if user_count else 0.0
    revenue_total = 0.0
    if "price" in bundle.orders.columns:
        revenue_total = float(pd.to_numeric(bundle.orders["price"], errors="coerce").fillna(0).sum())

    return {
        "objective": wf.objective,
        "dataset_summary": {
            "users": user_count,
            "orders": order_count,
            "items": item_count,
            "orders_per_user_avg": round(orders_per_user, 3),
            "revenue_total": round(revenue_total, 2),
        },
        "schema_profile": {
            "users": _safe_table_profile(bundle.users, "users"),
            "orders": _safe_table_profile(bundle.orders, "orders"),
            "items": _safe_table_profile(bundle.items, "items"),
        },
        "available_tools": {
            "schema_inspect": "sanitized schema/aggregates",
            "predict_execute": "run one approved PREDICT query via KumoRFM",
            "match_execute": "run one approved MATCH query",
            "result_summarize": "aggregate executed results",
        },
        "privacy_mode": {
            "raw_rows_shared_with_llm": False,
            "pii_policy": "PII columns are flagged, masked, or excluded before LLM context.",
        },
    }


def _risk_buckets_from_predictive_rows(rows: list[dict[str, Any]], score_key: str = "score") -> dict[str, Any]:
    low = 0
    medium = 0
    high = 0
    for r in rows:
        try:
            score = float(r.get(score_key, 0.0))
        except (TypeError, ValueError):
            score = 0.0
        if score >= 0.75:
            high += 1
        elif score >= 0.4:
            medium += 1
        else:
            low += 1
    return {"total": low + medium + high, "high": high, "medium": medium, "low": low}


def _masked_rows(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows[:limit]:
        masked: dict[str, Any] = {}
        for k, v in r.items():
            masked[k] = _mask_value(v) if _is_pii_column(str(k)) else v
        out.append(masked)
    return out


def _normalize_plan(raw: dict[str, Any], objective: str) -> dict[str, Any]:
    plan = raw.get("plan") if isinstance(raw.get("plan"), dict) else raw
    _need_fields(plan, ["goal_type", "plan_rationale", "steps", "tool_steps"], "plan")

    plan["objective"] = plan.get("objective") or objective
    if plan.get("goal_type") not in SUPPORTED_GOALS:
        raise ValueError("plan: unsupported goal_type")
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise ValueError("plan: steps must be a non-empty list")
    if not isinstance(plan.get("tool_steps"), list) or not plan["tool_steps"]:
        raise ValueError("plan: tool_steps must be a non-empty list")

    plan_text = " ".join(str(x) for x in plan.get("steps", []))
    for ts in plan.get("tool_steps", []):
        plan_text += " " + str(ts)
    lowered = plan_text.lower()
    for phrase in FORBIDDEN_PLAN_PHRASES:
        if phrase in lowered:
            raise ValueError(f"plan: Kumo-first plan cannot include '{phrase}'")

    clean_steps: list[dict[str, Any]] = []
    for step in plan["tool_steps"]:
        if not isinstance(step, dict):
            raise ValueError("plan: each tool_step must be an object")
        tool = step.get("tool")
        if tool not in ALLOWED_TOOLS:
            raise ValueError(f"plan: unsupported tool {tool}")
        query = str(step.get("query", "") or "").strip()
        if tool == "predict_execute" and not query.upper().startswith("PREDICT"):
            raise ValueError("plan: predict_execute requires a PREDICT query")
        if tool == "match_execute" and not query.upper().startswith("MATCH"):
            raise ValueError("plan: match_execute requires a MATCH query")
        clean_steps.append(
            {
                "step": int(step.get("step") or len(clean_steps) + 1),
                "tool": tool,
                "purpose": str(step.get("purpose", "")).strip(),
                "query": query,
            }
        )
    plan["tool_steps"] = clean_steps
    return plan


def _plan_from_llm(wf: GoalWorkflow, goal_ctx: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You are a fast KumoRFM goal-planning agent. Return STRICT JSON only. "
        "You are NOT building or training an ML model. KumoRFM is already the model. "
        "Do not propose feature engineering, model training, cross-validation, or custom ML algorithms. "
        "Use only the provided sanitized schema, aggregates, and available tools. "
        "If the goal misses a required value, set needs_clarification=true and ask concise clarification questions. "
        "Do not invent external variables, data sources, tables, or columns. "
        "Keep every string short."
    )
    context_json = json.dumps(goal_ctx, separators=(",", ":"))
    user = (
        f"Business goal: {wf.objective}\n"
        f"Sanitized context/tools: {context_json}\n"
        "Create a short human-reviewable execution plan.\n"
        "Use app-compatible query syntax only:\n"
        "- PREDICT churn_probability FOR EACH customer USING orders HORIZON N days RETURN score ORDER BY score DESC LIMIT 20\n"
        "- PREDICT purchase_likelihood FOR EACH customer USING orders HORIZON N days RETURN score ORDER BY score DESC LIMIT 20\n"
        "- PREDICT demand_forecast FOR EACH product USING orders, items HORIZON N days RETURN category, score, predicted_revenue ORDER BY score DESC LIMIT 20\n"
        "- MATCH customer RETURN user_id, active, age LIMIT 20\n"
        "Constraints: steps max 3 items; plan_rationale max 25 words; success_metric max 12 words; each purpose max 12 words.\n"
        "Return JSON schema exactly:\n"
        "{"
        '"goal_type":"churn_probability|purchase_likelihood|demand_forecast",'
        '"objective":"...",'
        '"needs_clarification":false,'
        '"clarifying_questions":[],'
        '"plan_rationale":"...",'
        '"success_metric":"...",'
        '"steps":["..."],'
        '"tool_steps":[{"step":1,"tool":"schema_inspect","purpose":"...","query":""},'
        '{"step":2,"tool":"predict_execute","purpose":"...","query":"PREDICT ..."},'
        '{"step":3,"tool":"match_execute","purpose":"...","query":"MATCH ..."},'
        '{"step":4,"tool":"result_summarize","purpose":"...","query":""}]'
        "}"
    )
    raw = _safe_json_llm(wf, "plan", system, user, max_tokens=900)
    return _normalize_plan(raw, wf.objective)


def _validate_tool_query(tool: str, query: str) -> None:
    q = query.strip()
    if tool == "predict_execute" and not q.upper().startswith("PREDICT"):
        raise ValueError("predict_execute can only run PREDICT queries")
    if tool == "match_execute" and not q.upper().startswith("MATCH"):
        raise ValueError("match_execute can only run MATCH queries")


def _run_plan_tools(wf: GoalWorkflow, bundle: RFMBundle) -> dict[str, Any]:
    tool_results: list[dict[str, Any]] = []
    predictive_rows: list[dict[str, Any]] = []
    factual_rows: list[dict[str, Any]] = []
    used_queries: list[dict[str, str]] = []

    for step in wf.plan.get("tool_steps", []):
        tool = step.get("tool")
        purpose = step.get("purpose", "")
        query = str(step.get("query", "") or "").strip()
        _log(wf, f"tool_{tool}", purpose or "Running planned tool", "tool")

        if tool == "schema_inspect":
            tool_results.append({"tool": tool, "status": "ok", "detail": "Sanitized schema already inspected for planning."})
            continue
        if tool == "result_summarize":
            tool_results.append({"tool": tool, "status": "ok", "detail": "Summary generated from prior tool results."})
            continue
        if tool not in {"predict_execute", "match_execute"}:
            raise ValueError(f"Unknown tool in plan: {tool}")

        _validate_tool_query(tool, query)
        result = execute(query, bundle)
        rows = result.get("results", [])
        used_queries.append({"tool": tool, "query": query})
        tool_results.append(
            {
                "tool": tool,
                "status": "ok",
                "query": query,
                "row_count": len(rows),
                "total_results": result.get("total_results", len(rows)),
            }
        )
        if tool == "predict_execute":
            predictive_rows.extend(rows)
        else:
            factual_rows.extend(rows)

    scores: list[float] = []
    for r in predictive_rows:
        try:
            scores.append(float(r.get("score", 0.0)))
        except (TypeError, ValueError):
            continue
    avg_top_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    return {
        "status": "executed",
        "avg_top_score": avg_top_score,
        "estimated_goal_movement_pct": None,
        "risk_buckets": _risk_buckets_from_predictive_rows(predictive_rows),
        "top_candidates": _masked_rows(predictive_rows, 10),
        "supporting_rows": _masked_rows(factual_rows, 10),
        "tool_results": tool_results,
        "used_queries": used_queries,
        "privacy_note": "Execution summary contains masked rows only; raw PII is not sent to the LLM.",
    }


def _actions_from_llm(wf: GoalWorkflow) -> list[dict[str, Any]]:
    system = (
        "Return STRICT JSON only. You are a KumoRFM business action agent. "
        "Recommend concise actions from the already-executed, privacy-safe summary. "
        "Do not suggest training a model or engineering features. Keep strings short."
    )
    summary = {
        "avg_top_score": wf.execution_summary.get("avg_top_score"),
        "risk_buckets": wf.execution_summary.get("risk_buckets"),
        "top_candidates": wf.execution_summary.get("top_candidates", [])[:5],
        "supporting_rows": wf.execution_summary.get("supporting_rows", [])[:5],
        "used_queries": wf.execution_summary.get("used_queries", []),
    }
    user = (
        f"Goal: {wf.objective}\n"
        f"Goal type: {wf.plan.get('goal_type')}\n"
        f"Privacy-safe execution summary: {json.dumps(summary, separators=(',', ':'))}\n"
        "Return JSON schema exactly: "
        '{"final_actions":[{"priority":1,"action":"...","target_group":"...",'
        '"reason":"...","expected_movement_pct":null}]}'
    )
    out = _safe_json_llm(wf, "actions", system, user, max_tokens=800)
    _need_fields(out, ["final_actions"], "actions")
    actions = out.get("final_actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions: final_actions must be a non-empty list")
    return actions[:5]


def _agent_payload(wf: GoalWorkflow, summary: str) -> dict[str, Any]:
    proposal: dict[str, Any] | None = None
    if wf.stage == "draft_plan":
        proposal = {"plan": wf.plan}
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
        "agent_logs": wf.logs[-80:],
        "query_type": "agent_goal",
    }


def _start_goal(user: str, objective: str, bundle: RFMBundle) -> dict[str, Any]:
    wf = GoalWorkflow(workflow_id=str(uuid4())[:8], user=user, objective=objective)
    _log(wf, "workflow_start", f"Objective received: {objective}")
    goal_ctx = _goal_context(bundle, wf)
    _log(wf, "privacy_context_built", "Using schema+aggregates+tool list; raw PII rows are blocked")

    try:
        wf.plan = _plan_from_llm(wf, goal_ctx)
        _log(wf, "workflow_initialized", f"Goal type selected: {wf.plan.get('goal_type')}")
    except Exception as e:
        wf.execution_summary = {
            "status": "needs_user_input",
            "detail": f"Agent could not create a valid Kumo-first plan: {e}",
        }
        _log(wf, "workflow_init_failed", str(e))

    WORKFLOWS[user] = wf
    return _agent_payload(
        wf,
        "Checkpoint A: Review the Kumo-first plan. Approve to execute it, or revise with `/goal revise <workflow_id> <changes>`.",
    )


def _approve_goal(user: str, bundle: RFMBundle, workflow_id: str | None) -> dict[str, Any]:
    wf = WORKFLOWS.get(user)
    if wf is None:
        return {"mode": "agent_goal", "summary": "No active workflow found. Start with `/goal <objective>`.", "query_type": "agent_goal"}
    if workflow_id and wf.workflow_id != workflow_id:
        return {"mode": "agent_goal", "summary": f"Workflow id mismatch. Active workflow is `{wf.workflow_id}`.", "query_type": "agent_goal"}

    _log(wf, "approve_received", f"Stage={wf.stage}")

    if wf.stage == "draft_plan":
        if not wf.plan:
            return _agent_payload(wf, "Plan is not valid yet. Revise the goal or plan before approval.")
        try:
            wf.execution_summary = _run_plan_tools(wf, bundle)
            wf.final_actions = _actions_from_llm(wf)
            wf.stage = "final_actions"
            wf.pending_approval = "final_actions"
            _log(wf, "stage_transition", "Plan executed; moved to final_actions checkpoint")
            return _agent_payload(
                wf,
                "Checkpoint B: Review final recommended actions. Approve to finalize, or revise with `/goal revise <workflow_id> ...`.",
            )
        except Exception as e:
            _log(wf, "execution_failed", str(e))
            wf.execution_summary = {
                "status": "needs_user_input",
                "detail": f"Plan execution failed: {e}",
            }
            return _agent_payload(wf, "Plan execution needs revision. Update the plan and approve again.")

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

    if wf.stage == "final_actions":
        system = "Return STRICT JSON only. Revise the final action list using only the existing privacy-safe execution summary."
        user_prompt = (
            f"Goal: {wf.objective}\nCurrent actions: {wf.final_actions}\n"
            f"Execution summary: {wf.execution_summary}\nRevision request: {revision}\n"
            'Return schema: {"final_actions":[{"priority":1,"action":"...","target_group":"...",'
            '"reason":"...","expected_movement_pct":null}],"revision_note":"..."}'
        )
        out = _safe_json_llm(wf, "revise_actions", system, user_prompt)
        _need_fields(out, ["final_actions"], "revise_actions")
        wf.final_actions = out["final_actions"][:5]
        _log(wf, "revise_applied", "Final actions revised")
        return _agent_payload(wf, "Final actions updated. Approve to finalize.")

    system = (
        "Return STRICT JSON only. Revise the Kumo-first plan. "
        "Do not propose feature engineering, model training, cross-validation, or external data."
    )
    user_prompt = (
        f"Goal: {wf.objective}\n"
        f"Current plan: {wf.plan}\n"
        f"Sanitized context and tools: {goal_ctx}\n"
        f"Revision request: {revision}\n"
        "Return the full revised plan using the same schema as the original plan."
    )
    raw = _safe_json_llm(wf, "revise_plan", system, user_prompt)
    wf.plan = _normalize_plan(raw, wf.objective)
    wf.execution_summary = {}
    wf.final_actions = []
    wf.stage = "draft_plan"
    wf.pending_approval = "plan"
    _log(wf, "revise_applied", "Plan revised")
    return _agent_payload(wf, "Plan updated. Approve when ready to execute.")


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
                "summary": "Please provide revision text after workflow id, e.g. `/goal revise 1234abcd make the horizon 45 days`.",
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
