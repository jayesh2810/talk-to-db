"""
PQL (Predictive Query Language) parser.

Handles two query modes:

  MATCH <entity>           — factual lookup, direct graph node filter
  PREDICT <type>           — predictive, multi-hop traversal + scoring

The parser extracts structured fields from a PQL string and returns a dict
that executor.py can act on without any further string processing.
"""

import re
from typing import Any


class PQLParseError(ValueError):
    """Raised when a PQL string cannot be parsed."""


# Normalize plural/variant entity names Claude might generate to graph node_type values
_ENTITY_MAP = {
    "customers": "customer",
    "products":  "product",
    "orders":    "order",
    "order_items": "item",
    "items":     "item",
    "interactions": "interaction",
    "campaigns": "campaign",
    "campaign_touchpoints": "campaign",
}


def _normalize_entity(name: str) -> str:
    """Map plural or variant entity names to canonical graph node_type."""
    return _ENTITY_MAP.get(name.lower(), name.lower())


def parse_pql(query: str) -> dict[str, Any]:
    """
    Parse a PQL query string into a structured execution plan.

    Returns a dict with at minimum:
      - mode: "factual" | "predictive"
      - raw: the original query string

    Factual MATCH query returns:
      - entity_type: str
      - filters: list[dict]
      - return_fields: list[str]
      - order_by: str | None
      - order_dir: "ASC" | "DESC"
      - limit: int

    Predictive PREDICT query returns:
      - prediction_type: str
      - entity_type: str
      - filters: list[dict]
      - using_tables: list[str]
      - horizon_days: int
      - return_fields: list[str]
      - limit: int
    """
    query = query.strip()
    upper = query.upper()

    if upper.startswith("PREDICT"):
        return _parse_predict(query)
    elif upper.startswith("MATCH"):
        return _parse_match(query)
    else:
        # Default to factual if ambiguous
        return _parse_match(query)


def _parse_match(query: str) -> dict[str, Any]:
    """Parse a MATCH (factual) PQL query."""
    result: dict[str, Any] = {
        "mode": "factual",
        "raw": query,
        "entity_type": "customer",
        "filters": [],
        "return_fields": [],
        "order_by": None,
        "order_dir": "DESC",
        "limit": 50,
    }

    # Entity type (first word after MATCH)
    m = re.search(r"MATCH\s+(\w+)", query, re.IGNORECASE)
    if m:
        result["entity_type"] = _normalize_entity(m.group(1))

    # WHERE clause filters
    result["filters"] = _parse_where(query)

    # RETURN fields
    result["return_fields"] = _parse_return(query)

    # ORDER BY
    m = re.search(r"ORDER\s+BY\s+([\w.]+)\s*(DESC|ASC)?", query, re.IGNORECASE)
    if m:
        field = m.group(1).split(".")[-1]  # strip entity prefix
        result["order_by"] = field
        result["order_dir"] = (m.group(2) or "DESC").upper()

    # LIMIT
    m = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
    if m:
        result["limit"] = int(m.group(1))

    return result


def _parse_predict(query: str) -> dict[str, Any]:
    """Parse a PREDICT (predictive) PQL query."""
    result: dict[str, Any] = {
        "mode": "predictive",
        "raw": query,
        "prediction_type": "churn_probability",
        "entity_type": "customer",
        "filters": [],
        "using_tables": [],
        "horizon_days": 90,
        "return_fields": [],
        "limit": 20,
    }

    # Prediction type (first word after PREDICT)
    m = re.search(r"PREDICT\s+(\w+)", query, re.IGNORECASE)
    if m:
        result["prediction_type"] = m.group(1).lower()

    # FOR EACH entity type
    m = re.search(r"FOR\s+EACH\s+([\w.]+)", query, re.IGNORECASE)
    if m:
        raw_entity = m.group(1).lower()
        # Handle "product.category" → entity_type = "category"
        if "." in raw_entity:
            result["entity_type"] = raw_entity.split(".")[-1]
        else:
            result["entity_type"] = _normalize_entity(raw_entity)

    # WHERE clause filters
    result["filters"] = _parse_where(query)

    # USING tables
    m = re.search(r"USING\s+([^\n]+?)(?:HORIZON|RETURN|ORDER|LIMIT|$)", query, re.IGNORECASE)
    if m:
        tables_str = m.group(1).strip()
        result["using_tables"] = [t.strip().lower() for t in tables_str.split(",")]

    # HORIZON
    m = re.search(r"HORIZON\s+(\d+)\s*(days?|months?|years?)?", query, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        unit = (m.group(2) or "days").lower()
        if unit.startswith("month"):
            n *= 30
        elif unit.startswith("year"):
            n *= 365
        result["horizon_days"] = n

    # RETURN fields
    result["return_fields"] = _parse_return(query)

    # LIMIT
    m = re.search(r"LIMIT\s+(\d+)", query, re.IGNORECASE)
    if m:
        result["limit"] = int(m.group(1))

    return result


def _parse_where(query: str) -> list[dict[str, Any]]:
    """
    Extract WHERE conditions from a PQL query.

    Supports:
      field = 'value'
      field != 'value'
      field >= value
      field <= value
      field > value
      field < value
    """
    filters: list[dict[str, Any]] = []

    where_m = re.search(
        r"WHERE\s+(.+?)(?:USING|RETURN|ORDER|LIMIT|HORIZON|FOR|$)",
        query,
        re.IGNORECASE | re.DOTALL,
    )
    if not where_m:
        return filters

    where_str = where_m.group(1).strip()
    # Split on AND (case-insensitive)
    clauses = re.split(r"\bAND\b", where_str, flags=re.IGNORECASE)

    for clause in clauses:
        clause = clause.strip()
        # Try >= <= != > < = in order of specificity
        for op in (">=", "<=", "!=", ">", "<", "="):
            parts = clause.split(op, 1)
            if len(parts) == 2:
                field = parts[0].strip()
                # Strip entity prefix (e.g. "customer.city" → "city")
                if "." in field:
                    field = field.split(".")[-1]
                value_raw = parts[1].strip().strip("'\"")
                # Try numeric coercion
                try:
                    value: Any = float(value_raw) if "." in value_raw else int(value_raw)
                except ValueError:
                    value = value_raw
                filters.append({"field": field, "op": op, "value": value})
                break

    return filters


def _parse_return(query: str) -> list[str]:
    """
    Extract the RETURN field list from a PQL query.

    Handles aggregate wrappers like COUNT(field), SUM(field), AVG(field)
    by unwrapping them to the inner field name, prefixed with the aggregate
    so executor.py can detect and handle them (e.g. "count:customer_id").
    """
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
        f = f.strip()

        # Detect aggregate functions: COUNT(...), SUM(...), AVG(...)
        agg_match = re.match(r"(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(.+?)\s*\)", f, re.IGNORECASE)
        if agg_match:
            agg_fn = agg_match.group(1).lower()
            inner = agg_match.group(2).strip()
            if "." in inner:
                inner = inner.split(".")[-1]
            fields.append(f"{agg_fn}:{inner.lower()}")
            continue

        if "." in f:
            f = f.split(".")[-1]  # strip entity prefix
        if f:
            fields.append(f.lower())

    return fields
