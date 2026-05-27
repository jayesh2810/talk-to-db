"""
PQL parser for KumoRFM-style queries.

Handles two query modes:
  - Factual (MATCH/SELECT): data lookup from pandas DataFrames
  - Predictive (PREDICT): forwarded directly to KumoRFM model.predict()

For predictive queries, the raw PQL string is the primary output since
KumoRFM consumes it directly. The parser extracts metadata for routing.
"""

import re
from typing import Any


class PQLParseError(ValueError):
    """Raised when a PQL string cannot be parsed."""


# Map entity names to table names in the dataset
_TABLE_MAP = {
    "users": "users",
    "user": "users",
    "customers": "users",
    "customer": "users",
    "items": "items",
    "item": "items",
    "products": "items",
    "product": "items",
    "orders": "orders",
    "order": "orders",
}

# Normalize raw entity tokens to the canonical names the executors branch on.
# Factual executor (rfm.factual) accepts customer/user/users/product/item/items/order/orders.
# Predictive executor (rfm.predict) special-cases entity in {"product", "item", "category"}.
_ENTITY_NORMALIZE = {
    "customer": "customer",
    "customers": "customer",
    "user": "customer",
    "users": "customer",
    "product": "product",
    "products": "product",
    "item": "product",
    "items": "product",
    "order": "order",
    "orders": "order",
    "category": "category",
    "categories": "category",
}

_PREDICT_TYPES = (
    "churn_probability",
    "purchase_likelihood",
    "demand_forecast",
    "fraud_risk",
)

# Clause keywords used as stop-markers when parsing sub-fragments.
_CLAUSE_STOP = r"(?=\s+(?:WHERE|USING|HORIZON|RETURN|ORDER|LIMIT)\b|\s*$)"


def _resolve_table(name: str) -> str:
    return _TABLE_MAP.get(name.lower(), name.lower())


def _normalize_entity(name: str) -> str:
    return _ENTITY_NORMALIZE.get(name.lower(), name.lower())


def parse_pql(query: str) -> dict[str, Any]:
    """
    Parse a PQL query string into a structured execution plan.

    Returns a dict with at minimum:
      - mode: "factual" | "predictive"
      - raw: the original query string

    Factual queries also include: table, entity_type, filters, return_fields,
      order_by, order_dir, limit
    Predictive queries also include: prediction_type, predict_target,
      entity_type, entity_table, entity_spec, horizon_days, filters,
      return_fields, order_by, order_dir, limit, indices
    """
    query = query.strip()
    upper = query.upper()

    if upper.startswith("PREDICT"):
        return _parse_predict(query)
    elif upper.startswith("MATCH") or upper.startswith("SELECT"):
        return _parse_factual(query)
    else:
        return _parse_factual(query)


def _parse_factual(query: str) -> dict[str, Any]:
    """Parse a factual (MATCH/SELECT) query for pandas execution."""
    result: dict[str, Any] = {
        "mode": "factual",
        "raw": query,
        "table": "users",
        "entity_type": "customer",
        "filters": [],
        "return_fields": [],
        "order_by": None,
        "order_dir": "DESC",
        "limit": 50,
    }

    m = re.search(r"(?:MATCH|SELECT\s+\*\s+FROM|FROM)\s+(\w+)", query, re.IGNORECASE)
    if m:
        raw_entity = m.group(1)
        result["table"] = _resolve_table(raw_entity)
        result["entity_type"] = _normalize_entity(raw_entity)

    result["filters"] = _parse_where(query)
    result["return_fields"] = _parse_return(query)

    m = re.search(r"ORDER\s+BY\s+([\w.]+)\s*(DESC|ASC)?", query, re.IGNORECASE)
    if m:
        result["order_by"] = m.group(1).split(".")[-1]
        result["order_dir"] = (m.group(2) or "DESC").upper()

    m = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
    if m:
        result["limit"] = int(m.group(1))

    return result


def _parse_predict(query: str) -> dict[str, Any]:
    """
    Parse a KumoRFM-style PREDICT query.

    Emits the keys the predictive executor reads: ``prediction_type``,
    ``entity_type``, ``horizon_days``, ``filters``, ``limit``, plus the
    legacy ``predict_target`` / ``entity_spec`` / ``indices`` for display.
    """
    result: dict[str, Any] = {
        "mode": "predictive",
        "raw": query,
        "predict_target": "",
        "prediction_type": "",
        "entity_table": "",
        "entity_type": "customer",
        "entity_spec": "",
        "indices": None,
        "horizon_days": 90,
        "limit": 20,
        "filters": [],
        "return_fields": [],
        "order_by": None,
        "order_dir": "DESC",
    }

    # PREDICT <target> FOR ...
    m = re.search(r"PREDICT\s+(.+?)\s+FOR\s+", query, re.IGNORECASE | re.DOTALL)
    if m:
        target = m.group(1).strip()
        result["predict_target"] = target
        target_lower = target.lower()
        matched_type = ""
        for ptype in _PREDICT_TYPES:
            if ptype in target_lower:
                matched_type = ptype
                break
        result["prediction_type"] = matched_type or target_lower

    # FOR [EACH] <entity-or-dotted-spec>
    m = re.search(
        r"FOR\s+(?:EACH\s+)?([\w.]+)",
        query,
        re.IGNORECASE,
    )
    if m:
        spec = m.group(1).strip()
        result["entity_spec"] = spec
        if "." in spec:
            table = spec.split(".", 1)[0]
            result["entity_table"] = table
            result["entity_type"] = _normalize_entity(table)
        else:
            result["entity_type"] = _normalize_entity(spec)
            result["entity_table"] = _resolve_table(spec)

    # HORIZON N (days|weeks|months) — normalize to days
    m = re.search(
        r"HORIZON\s+(\d+)\s*(day|days|week|weeks|month|months)?",
        query,
        re.IGNORECASE,
    )
    if m:
        n = int(m.group(1))
        unit = (m.group(2) or "days").lower()
        if "week" in unit:
            n *= 7
        elif "month" in unit:
            n *= 30
        result["horizon_days"] = n

    result["filters"] = _parse_where(query)
    result["return_fields"] = _parse_return(query)

    m = re.search(r"ORDER\s+BY\s+([\w.]+)\s*(DESC|ASC)?", query, re.IGNORECASE)
    if m:
        result["order_by"] = m.group(1).split(".")[-1]
        result["order_dir"] = (m.group(2) or "DESC").upper()

    m = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
    if m:
        result["limit"] = int(m.group(1))

    # Optional: entity IN (...) for explicit index lists
    in_match = re.search(
        r"FOR\s+(?:EACH\s+)?[\w.]+\s+IN\s*\(([^)]+)\)",
        query,
        re.IGNORECASE,
    )
    if in_match:
        indices_str = in_match.group(1)
        try:
            result["indices"] = [
                int(x.strip()) if x.strip().lstrip("-").isdigit()
                else x.strip().strip("'\"")
                for x in indices_str.split(",")
            ]
        except ValueError:
            pass

    return result


def _parse_where(query: str) -> list[dict[str, Any]]:
    """Extract WHERE conditions, stopping at the next clause keyword."""
    filters: list[dict[str, Any]] = []

    where_m = re.search(
        r"WHERE\s+(.+?)" + _CLAUSE_STOP,
        query,
        re.IGNORECASE | re.DOTALL,
    )
    if not where_m:
        return filters

    where_str = where_m.group(1).strip()
    clauses = re.split(r"\bAND\b", where_str, flags=re.IGNORECASE)

    for clause in clauses:
        clause = clause.strip()
        for op in (">=", "<=", "!=", ">", "<", "="):
            parts = clause.split(op, 1)
            if len(parts) == 2:
                field = parts[0].strip().split(".")[-1]
                value_raw = parts[1].strip().strip("'\"")
                try:
                    value: Any = float(value_raw) if "." in value_raw else int(value_raw)
                except ValueError:
                    value = value_raw
                filters.append({"field": field, "op": op, "value": value})
                break

    return filters


def _parse_return(query: str) -> list[str]:
    """Extract RETURN field list."""
    m = re.search(
        r"RETURN\s+(.+?)(?:ORDER\s+BY|LIMIT|$)",
        query,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []

    fields_str = m.group(1).strip()
    fields = []
    for f in fields_str.split(","):
        f = f.strip().split(".")[-1]
        if f:
            fields.append(f.lower())
    return fields
