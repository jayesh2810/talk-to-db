"""
Run KumoRFM predictions from parsed PQL plans (maps to Kumo PQL + indices).
"""

from __future__ import annotations

import math
import os
from typing import Any

import pandas as pd

from rfm.cache import RFMBundle


def _sanitize(obj: Any) -> Any:
    """Convert numpy/pandas scalars so FastAPI JSON serialization succeeds."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return obj
    if hasattr(obj, "item"):
        try:
            return _sanitize(obj.item())
        except Exception:
            pass
    try:
        v = float(obj)
        if not math.isfinite(v):
            return None
        iv = int(v)
        if abs(v - iv) < 1e-9:
            return iv
        return v
    except (TypeError, ValueError):
        return obj


def _optional_int(val: Any) -> int | None:
    if val is None or (isinstance(val, (float,)) and not math.isfinite(val)):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _optional_bool(val: Any) -> bool | None:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return bool(val)
    except (TypeError, ValueError):
        return None


_TRAVERSAL_KUMO = [
    {
        "step": 1,
        "hop": 1,
        "description": "KumoRFM relational prediction",
        "detail": (
            "Zero-shot inference on cached users/items/orders graph "
            "(see https://kumo.ai/docs/quick-start/rfm/). "
            "Neighborhood sampling over the relational graph replaces hand-written multi-hop traversal."
        ),
    },
]


def _run_mode() -> str:
    return os.environ.get("KUMO_RFM_RUN_MODE", "fast").strip().lower()


def _score_column_binary(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        cl = c.lower()
        if cl == "true_prob" or cl.endswith("_true_prob"):
            return c
    if "TARGET_PRED" in df.columns:
        return "TARGET_PRED"
    return None


def _entity_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if str(c).upper() == "ENTITY":
            return c
    return df.columns[0]


def _score_column_regression(df: pd.DataFrame) -> str | None:
    if "TARGET_PRED" in df.columns:
        return "TARGET_PRED"
    for c in df.columns:
        if "pred" in c.lower() and "prob" not in c.lower():
            return c
    return None


def _normalize_prob_series(df: pd.DataFrame, prefer_positive_class: bool) -> pd.Series:
    """Return a score in [0,1] for sorting / display."""
    col = _score_column_binary(df)
    if col:
        s = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return s.clip(0.0, 1.0)

    col_r = _score_column_regression(df)
    if col_r:
        v = pd.to_numeric(df[col_r], errors="coerce").fillna(0.0)
        if v.max() > 1.0 or v.min() < 0.0:
            rng = (v.max() - v.min()) or 1.0
            return ((v - v.min()) / rng).clip(0.0, 1.0)
        return v.clip(0.0, 1.0)

    return pd.Series(0.0, index=df.index)


def _apply_user_filters(users: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    out = users
    for f in filters:
        field = f.get("field", "")
        op = f.get("op", "=")
        val = f.get("value")
        if field not in users.columns:
            continue
        col = out[field]
        if field == "active" and isinstance(val, str):
            val = val.lower() in ("true", "1", "yes")
        try:
            if op == "=":
                out = out[col == val]
            elif op == "!=":
                out = out[col != val]
            elif op == ">":
                out = out[col > float(val)]
            elif op == "<":
                out = out[col < float(val)]
            elif op == ">=":
                out = out[col >= float(val)]
            elif op == "<=":
                out = out[col <= float(val)]
        except Exception:
            continue
    return out


def _apply_item_filters(items: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
    out = items
    for f in filters:
        field = f.get("field", "")
        op = f.get("op", "=")
        val = f.get("value")
        if field not in items.columns:
            continue
        col = out[field]
        try:
            if op == "=":
                out = out[col.astype(str) == str(val)]
            elif op == "!=":
                out = out[col.astype(str) != str(val)]
        except Exception:
            continue
    return out


def _kumo_pql_churn(horizon: int) -> str:
    return f"PREDICT COUNT(orders.*, 0, {horizon}, days)=0 FOR EACH users.user_id"


def _kumo_pql_purchase(horizon: int) -> str:
    return f"PREDICT COUNT(orders.*, 0, {horizon}, days) > 0 FOR EACH users.user_id"


def _kumo_pql_demand(horizon: int) -> str:
    return f"PREDICT SUM(orders.price, 0, {horizon}, days) FOR EACH items.item_id"


def churn_score_for_user(
    bundle: RFMBundle,
    user_id: int,
    *,
    horizon_days: int = 90,
) -> tuple[float, float, list[dict[str, Any]]]:
    """Single-user churn-style score from KumoRFM (same PQL as batch churn path)."""
    users = bundle.users
    if user_id not in set(users["user_id"].tolist()):
        raise ValueError(f"Unknown user_id: {user_id}")

    q = _kumo_pql_churn(horizon_days)
    with bundle.model.batch_mode(batch_size="max", num_retries=1):
        raw = bundle.model.predict(q, indices=[user_id], run_mode=_run_mode())

    scores = _normalize_prob_series(raw, True)
    sc = float(scores.iloc[0]) if len(scores) else 0.0
    if not math.isfinite(sc):
        sc = 0.0
    conf = round(min(abs(sc - 0.5) * 2, 1.0), 3)
    factors = [{"factor": "kumorfm_churn_proxy", "contribution": round(sc, 4), "raw_value": sc}]
    return sc, conf, factors


def run_predictive(
    bundle: RFMBundle,
    plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute predictive plan via KumoRFM. Returns same shape as executor._execute_predictive rows.
    """
    ptype = plan.get("prediction_type", "churn_probability")
    horizon = int(plan.get("horizon_days") or 90)
    limit = int(plan.get("limit") or 20)
    filters = plan.get("filters") or []
    entity = plan.get("entity_type") or "customer"

    model = bundle.model
    users = bundle.users
    items = bundle.items

    if ptype == "fraud_risk":
        raise ValueError(
            "fraud_risk is not available on the Kumo online-shopping RFM dataset. "
            "Try purchase_likelihood or churn_probability."
        )

    run_mode = _run_mode()

    if ptype == "demand_forecast" or entity in ("product", "item", "category"):
        # Demand at item grain; category filters applied post-hoc
        q = _kumo_pql_demand(horizon)
        idx_df = _apply_item_filters(items, filters)
        indices = idx_df["item_id"].tolist()
        if not indices:
            return {
                "query_type": "predictive",
                "results": [],
                "traversal_steps": _TRAVERSAL_KUMO,
                "columns": ["category", "item_id", "item_name", "score", "predicted_revenue"],
                "total_results": 0,
            }

        with model.batch_mode(batch_size="max", num_retries=1):
            raw = model.predict(q, indices=indices, run_mode=run_mode)

        pred_col = _score_column_regression(raw) or "TARGET_PRED"
        scores = _normalize_prob_series(raw, True)
        ec = _entity_col(raw)
        merged = raw.assign(_score=scores).merge(
            items[["item_id", "category", "item_name"]],
            left_on=ec,
            right_on="item_id",
            how="left",
        )

        rows_m = []
        for _, row in merged.iterrows():
            rev = float(row.get(pred_col, 0) or 0)
            iid = row[ec] if ec in row.index else row.get("ENTITY", "")
            rows_m.append(
                {
                    "category": row.get("category", ""),
                    "item_id": iid,
                    "item_name": row.get("item_name", ""),
                    "score": float(row["_score"]),
                    "predicted_revenue": round(rev, 2),
                    "confidence": None,
                    "top_factors": [],
                }
            )

        rows_m.sort(key=lambda r: r["predicted_revenue"], reverse=True)
        total = len(rows_m)
        out_rows = rows_m[:limit]

        return {
            "query_type": "predictive",
            "results": _sanitize(out_rows),
            "traversal_steps": _TRAVERSAL_KUMO,
            "columns": ["category", "item_id", "item_name", "score", "predicted_revenue", "confidence", "top_factors"],
            "total_results": total,
        }

    # User-centric: churn + purchase
    idx_df = _apply_user_filters(users, filters)
    indices = idx_df["user_id"].tolist()
    if not indices:
        return {
            "query_type": "predictive",
            "results": [],
            "traversal_steps": _TRAVERSAL_KUMO,
            "columns": [],
            "total_results": 0,
        }

    if ptype == "purchase_likelihood":
        q = _kumo_pql_purchase(horizon)
    else:
        # churn_probability and unknown → churn-style
        q = _kumo_pql_churn(horizon)

    with model.batch_mode(batch_size="max", num_retries=1):
        raw = model.predict(q, indices=indices, run_mode=run_mode)

    scores = _normalize_prob_series(raw, True)
    raw = raw.assign(_score=scores)

    rows_out: list[dict[str, Any]] = []
    ent_col = _entity_col(raw)

    for _, row in raw.iterrows():
        uid = row[ent_col]
        sc = float(row["_score"])
        if not math.isfinite(sc):
            sc = 0.0
        try:
            uid_key: Any = int(float(uid))
        except (TypeError, ValueError):
            uid_key = uid
        umatch = users[users["user_id"] == uid_key]
        age = _optional_int(umatch["age"].iloc[0]) if len(umatch) else None
        active = _optional_bool(umatch["active"].iloc[0]) if len(umatch) else None

        seg = "unknown"
        if active is True:
            seg = "active"
        elif active is False:
            seg = "inactive"

        rows_out.append(
            {
                "user_id": uid,
                "name": f"user_{uid}",
                "segment": seg,
                "city": "",
                "score": round(sc, 4),
                "confidence": round(min(abs(sc - 0.5) * 2, 1.0), 3),
                "top_factors": [
                    {"factor": "kumorfm_binary_score", "contribution": round(sc, 4), "raw_value": sc},
                    {"factor": "user_age", "contribution": 0.0, "raw_value": age},
                ],
                "recommended_action": (
                    "Prioritize outreach using KumoRFM-ranked scores "
                    "(prescriptive templates can combine explain=true per entity)."
                ),
                "success_probability": 0.0,
            }
        )

    rows_out.sort(key=lambda x: x["score"], reverse=True)
    total = len(rows_out)
    rows_out = rows_out[:limit]

    return {
        "query_type": "predictive",
        "results": _sanitize(rows_out),
        "traversal_steps": _TRAVERSAL_KUMO,
        "columns": [
            "user_id",
            "name",
            "segment",
            "city",
            "score",
            "confidence",
            "top_factors",
            "recommended_action",
            "success_probability",
        ],
        "total_results": total,
    }
