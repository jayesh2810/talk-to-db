"""
Factual MATCH queries against Kumo online-shopping parquet (same data as LocalGraph / KumoRFM).

When ``RFMBundle`` is loaded (always at startup), factual ``MATCH`` queries filter the same cached
users/items/orders tables used by ``LocalGraph``.
"""

from __future__ import annotations

import math
import operator
from typing import Any

import pandas as pd

from rfm.cache import RFMBundle
from rfm.predict import _sanitize

_OPS = {
    "=": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}

_ENTITY_TABLE = {
    "customer": "users",
    "users": "users",
    "user": "users",
    "product": "items",
    "item": "items",
    "items": "items",
    "order": "orders",
    "orders": "orders",
}

_FIELD_ALIASES = {
    "users": {"customer_id": "user_id"},
    "items": {"product_id": "item_id"},
    "orders": {"customer_id": "user_id", "product_id": "item_id"},
}

# When PQL has no ORDER BY, sort by primary key ascending so LIMIT behaves predictably.
_PRIMARY_SORT_KEY = {
    "users": "user_id",
    "items": "item_id",
    "orders": "order_id",
}

_TRAVERSAL_KUMO_FACTUAL = [
    {
        "step": 1,
        "hop": 0,
        "description": "KumoRFM dataset (relational lookup)",
        "detail": (
            "Rows filtered from cached users/items/orders parquet - "
            "same tables as the LocalGraph used by KumoRFM."
        ),
    },
]


def _resolve_order_column(df: pd.DataFrame, order_by: str | None, table: str) -> str | None:
    if not order_by:
        return None
    aliases = _FIELD_ALIASES.get(table, {})
    col = aliases.get(order_by, order_by)
    return col if col in df.columns else None


def _normalize_scalar(val: Any, *, field: str, sample_series: pd.Series) -> Any:
    if field == "active" and isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    if pd.api.types.is_datetime64_any_dtype(sample_series.dtype):
        try:
            return pd.Timestamp(val)
        except Exception:
            return val
    if pd.api.types.is_bool_dtype(sample_series.dtype):
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)
    if pd.api.types.is_numeric_dtype(sample_series.dtype):
        try:
            return float(val) if "." in str(val) else int(float(val))
        except (TypeError, ValueError):
            return val
    return val


def _apply_filters_df(
    df: pd.DataFrame,
    filters: list[dict[str, Any]],
    table: str,
) -> pd.DataFrame:
    aliases = _FIELD_ALIASES.get(table, {})
    out = df
    for f in filters:
        raw_field = f.get("field", "")
        field = aliases.get(raw_field, raw_field)
        if field not in out.columns:
            continue
        op = f.get("op", "=")
        expected_raw = f.get("value")
        col = out[field]
        cmp_fn = _OPS.get(op)
        if cmp_fn is None:
            continue

        try:
            if pd.api.types.is_datetime64_any_dtype(col.dtype):
                left = pd.to_datetime(col, errors="coerce")
                try:
                    right = pd.Timestamp(expected_raw)
                except Exception:
                    continue
                if op == "=":
                    mask = left == right
                elif op == "!=":
                    mask = left != right
                elif op == ">":
                    mask = left > right
                elif op == "<":
                    mask = left < right
                elif op == ">=":
                    mask = left >= right
                elif op == "<=":
                    mask = left <= right
                else:
                    continue
            elif field == "active" or pd.api.types.is_bool_dtype(col.dtype):
                ev = _normalize_scalar(expected_raw, field=field, sample_series=col)
                left = col.astype(bool) if col.dtype != bool else col
                if op == "=":
                    mask = left == bool(ev)
                elif op == "!=":
                    mask = left != bool(ev)
                else:
                    continue
            elif pd.api.types.is_numeric_dtype(col.dtype):
                left = pd.to_numeric(col, errors="coerce")
                try:
                    exp = float(expected_raw) if "." in str(expected_raw) else int(float(expected_raw))
                    exp_f = float(exp)
                except (TypeError, ValueError):
                    continue
                mask = cmp_fn(left, exp_f)
            else:
                left = col.astype(str)
                exp_s = str(expected_raw).strip("'\"") if expected_raw is not None else ""
                mask = cmp_fn(left, str(exp_s))
            out = out.loc[mask].copy()
        except Exception:
            continue
    return out


def _dataframe_for_entity(bundle: RFMBundle, entity_type: str) -> tuple[pd.DataFrame, str] | tuple[None, None]:
    table = _ENTITY_TABLE.get(entity_type)
    if table == "users":
        return bundle.users.copy(), "users"
    if table == "items":
        return bundle.items.copy(), "items"
    if table == "orders":
        return bundle.orders.copy(), "orders"
    return None, None


def run_factual(bundle: RFMBundle, plan: dict[str, Any]) -> dict[str, Any]:
    """Execute a MATCH plan on cached Kumo tables; same response shape as executor._execute_factual."""
    entity_type = plan.get("entity_type") or "customer"
    filters = plan.get("filters") or []
    return_fields = plan.get("return_fields") or []
    order_by = plan.get("order_by")
    order_dir = plan.get("order_dir") or "DESC"
    limit = int(plan.get("limit") or 50)

    df, table = _dataframe_for_entity(bundle, entity_type)
    if df is None or table is None:
        return {
            "query_type": "factual",
            "results": [],
            "traversal_steps": _TRAVERSAL_KUMO_FACTUAL,
            "columns": [],
            "total_results": 0,
        }

    df = _apply_filters_df(df, filters, table)
    aliases = _FIELD_ALIASES.get(table, {})

    agg_fields = [f for f in return_fields if ":" in f]
    plain_fields = [f for f in return_fields if ":" not in f]

    if agg_fields and not plain_fields:
        agg_row: dict[str, Any] = {}
        total = len(df)
        for af in agg_fields:
            fn, inner = af.split(":", 1)
            inner_res = aliases.get(inner, inner)
            if fn == "count":
                agg_row[f"count_{inner}"] = total
            elif inner_res in df.columns:
                series = pd.to_numeric(df[inner_res], errors="coerce").dropna()
                if fn == "sum":
                    agg_row[f"sum_{inner}"] = round(float(series.sum()), 2) if len(series) else 0.0
                elif fn == "avg":
                    agg_row[f"avg_{inner}"] = round(float(series.mean()), 2) if len(series) else 0.0
                elif fn == "min":
                    agg_row[f"min_{inner}"] = round(float(series.min()), 2) if len(series) else 0.0
                elif fn == "max":
                    agg_row[f"max_{inner}"] = round(float(series.max()), 2) if len(series) else 0.0
        result_rows = [agg_row]
        return {
            "query_type": "factual",
            "results": _sanitize(result_rows),
            "traversal_steps": _TRAVERSAL_KUMO_FACTUAL,
            "columns": list(agg_row.keys()),
            "total_results": 1,
        }

    ob_col = _resolve_order_column(df, order_by, table)
    if ob_col:
        ascending = str(order_dir).upper() == "ASC"
        df = df.sort_values(by=ob_col, ascending=ascending, na_position="last")
    else:
        pk = _PRIMARY_SORT_KEY.get(table)
        if pk and pk in df.columns:
            df = df.sort_values(by=pk, ascending=True, na_position="last")

    total = len(df)
    df = df.head(limit)

    records = df.to_dict(orient="records")
    rows: list[dict[str, Any]] = []
    for raw in records:
        row = {k: (None if (isinstance(v, float) and not math.isfinite(v)) else v) for k, v in raw.items()}
        rows.append(row)

    if plain_fields:
        projected: list[dict[str, Any]] = []
        for r in rows:
            proj: dict[str, Any] = {}
            for pf in plain_fields:
                key = aliases.get(pf, pf)
                proj[pf] = r.get(key, "")
            projected.append(proj)
        rows = projected
        columns = plain_fields
    else:
        columns = list(rows[0].keys()) if rows else []

    return {
        "query_type": "factual",
        "results": _sanitize(rows),
        "traversal_steps": _TRAVERSAL_KUMO_FACTUAL,
        "columns": columns,
        "total_results": total,
    }
