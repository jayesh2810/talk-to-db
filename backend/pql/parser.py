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


def _resolve_table(name: str) -> str:
    return _TABLE_MAP.get(name.lower(), name.lower())


def parse_pql(query: str) -> dict[str, Any]:
    """
    Parse a PQL query string into a structured execution plan.

    Returns a dict with at minimum:
      - mode: "factual" | "predictive"
      - raw: the original query string

    Factual queries also include: table, filters, return_fields, order_by, limit
    Predictive queries also include: predict_target, entity_table, entity_spec
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
        "filters": [],
        "return_fields": [],
        "order_by": None,
        "order_dir": "DESC",
        "limit": 50,
    }

    m = re.search(r"(?:MATCH|SELECT\s+\*\s+FROM|FROM)\s+(\w+)", query, re.IGNORECASE)
    if m:
        result["table"] = _resolve_table(m.group(1))

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

    The raw PQL string is forwarded to model.predict(), so we extract
    just enough metadata for routing and display.
    """
    result: dict[str, Any] = {
        "mode": "predictive",
        "raw": query,
        "predict_target": "",
        "entity_table": "",
        "entity_spec": "",
        "indices": None,
    }

    # Extract the full PREDICT target expression
    m = re.search(r"PREDICT\s+(.+?)\s+FOR\s+", query, re.IGNORECASE)
    if m:
        result["predict_target"] = m.group(1).strip()

    # Extract entity spec (e.g., "users.user_id=42" or "users.user_id IN (1,2,3)")
    m = re.search(r"FOR\s+(.+?)(?:\s+WHERE|\s*$)", query, re.IGNORECASE)
    if m:
        entity_spec = m.group(1).strip()
        result["entity_spec"] = entity_spec

        # Extract table name from entity spec
        table_match = re.match(r"(\w+)\.", entity_spec)
        if table_match:
            result["entity_table"] = table_match.group(1)

        # Extract indices if IN (...) syntax is used
        in_match = re.search(r"IN\s*\(([^)]+)\)", entity_spec, re.IGNORECASE)
        if in_match:
            indices_str = in_match.group(1)
            try:
                result["indices"] = [
                    int(x.strip()) if x.strip().isdigit() else x.strip().strip("'\"")
                    for x in indices_str.split(",")
                ]
            except ValueError:
                pass

    return result


def _parse_where(query: str) -> list[dict[str, Any]]:
    """Extract WHERE conditions."""
    filters: list[dict[str, Any]] = []

    where_m = re.search(
        r"WHERE\s+(.+?)(?:RETURN|ORDER|LIMIT|$)",
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
