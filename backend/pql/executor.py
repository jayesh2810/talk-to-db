"""
PQL execution engine.

Routes parsed PQL plans to either:
  - Factual path: direct graph node lookup with filter/sort/limit
  - Predictive path: multi-hop traversal → signal collection → weighted scoring
"""

import operator
from typing import Any

# Map full state names → 2-letter codes used in seed data
_STATE_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def _normalize_filter_value(field: str, value: Any) -> Any:
    """Normalize filter values to match seed data conventions."""
    if field == "state" and isinstance(value, str) and len(value) > 2:
        return _STATE_ABBREV.get(value.lower(), value)
    return value

import networkx as nx

from pql.parser import parse_pql
from graph.traversal import (
    collect_churn_signals,
    collect_purchase_signals,
    collect_fraud_signals,
    collect_demand_signals,
)
from prediction.engine import (
    score_churn,
    score_purchase_likelihood,
    score_fraud_risk,
    score_demand,
    get_prescriptive_action,
)
from models.schemas import TraversalStep

# Comparison operators for WHERE filter evaluation
_OPS = {
    "=":  operator.eq,
    "!=": operator.ne,
    ">":  operator.gt,
    "<":  operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


def execute(G: nx.DiGraph, pql_query: str) -> dict[str, Any]:
    """
    Parse and execute a PQL query against the graph.

    Returns a dict with:
      - query_type: "factual" | "predictive"
      - results: list of row dicts
      - traversal_steps: list of TraversalStep dicts
      - columns: list of column names for the result table
      - total_results: int (before LIMIT)
    """
    plan = parse_pql(pql_query)

    if plan["mode"] == "factual":
        return _execute_factual(G, plan)
    else:
        return _execute_predictive(G, plan)


# ─── Factual execution ────────────────────────────────────────────────────────

def _execute_factual(G: nx.DiGraph, plan: dict) -> dict[str, Any]:
    """Direct graph node lookup — no scoring, no traversal."""
    entity_type = plan["entity_type"]
    filters = plan["filters"]
    return_fields = plan["return_fields"]
    order_by = plan.get("order_by")
    order_dir = plan.get("order_dir", "DESC")
    limit = plan.get("limit", 50)

    # Collect all nodes of the requested type
    rows: list[dict[str, Any]] = []
    for node_id, attrs in G.nodes(data=True):
        if attrs.get("node_type") != entity_type:
            continue
        if not _apply_filters(attrs, filters):
            continue
        rows.append(dict(attrs))

    # Sort
    if order_by and rows:
        reverse = order_dir == "DESC"
        rows.sort(
            key=lambda r: _sort_key(r.get(order_by, 0)),
            reverse=reverse,
        )

    total = len(rows)

    # Handle aggregate-only RETURN (e.g. RETURN COUNT(customer_id))
    agg_fields = [f for f in return_fields if ":" in f]
    plain_fields = [f for f in return_fields if ":" not in f]

    if agg_fields and not plain_fields:
        # Pure aggregate query — collapse all rows into one summary row
        agg_row: dict[str, Any] = {}
        for af in agg_fields:
            fn, field = af.split(":", 1)
            if fn == "count":
                agg_row[f"count_{field}"] = total
            elif fn in ("sum", "avg", "min", "max"):
                values = [_sort_key(r.get(field, 0)) for r in rows]
                if fn == "sum":
                    agg_row[f"sum_{field}"] = round(sum(values), 2)
                elif fn == "avg":
                    agg_row[f"avg_{field}"] = round(sum(values) / len(values), 2) if values else 0
                elif fn == "min":
                    agg_row[f"min_{field}"] = min(values) if values else 0
                elif fn == "max":
                    agg_row[f"max_{field}"] = max(values) if values else 0
        result_rows = [agg_row]
        columns = list(agg_row.keys())
        return {
            "query_type": "factual",
            "results": result_rows,
            "traversal_steps": [],
            "columns": columns,
            "total_results": 1,
        }

    rows = rows[:limit]

    # Project return fields (if specified)
    if plain_fields:
        rows = [_project(r, plain_fields) for r in rows]
    else:
        rows = [_clean_row(r) for r in rows]

    columns = list(rows[0].keys()) if rows else plain_fields or []

    return {
        "query_type": "factual",
        "results": rows,
        "traversal_steps": [],
        "columns": columns,
        "total_results": total,
    }


def _apply_filters(attrs: dict, filters: list[dict]) -> bool:
    """Return True if the node attributes satisfy all WHERE conditions."""
    for f in filters:
        field = f["field"]
        op = f["op"]
        expected = _normalize_filter_value(field, f["value"])
        actual = attrs.get(field)

        if actual is None or actual == "":
            return False

        # Coerce types for comparison
        try:
            if isinstance(expected, (int, float)):
                actual = float(actual)
            cmp_fn = _OPS.get(op)
            if cmp_fn and not cmp_fn(actual, expected):
                return False
        except (TypeError, ValueError):
            if op == "=" and str(actual).lower() != str(expected).lower():
                return False
            elif op == "!=" and str(actual).lower() == str(expected).lower():
                return False

    return True


def _sort_key(value: Any) -> float:
    """Convert a value to a float for sorting (string values sort as 0)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _project(row: dict, fields: list[str]) -> dict:
    """Select only the requested return fields from a row."""
    return {f: row.get(f, "") for f in fields}


def _clean_row(row: dict) -> dict:
    """Remove internal graph fields from a result row."""
    skip = {"node_type"}
    return {k: v for k, v in row.items() if k not in skip and not k.startswith("_")}


# ─── Predictive execution ─────────────────────────────────────────────────────

def _execute_predictive(G: nx.DiGraph, plan: dict) -> dict[str, Any]:
    """Multi-hop traversal + weighted scoring for predictive queries."""
    prediction_type = plan["prediction_type"]
    entity_type = plan["entity_type"]
    filters = plan.get("filters", [])
    limit = plan.get("limit", 20)

    if prediction_type == "churn_probability":
        return _run_churn(G, filters, limit)
    elif prediction_type == "purchase_likelihood":
        return _run_purchase(G, filters, limit)
    elif prediction_type == "fraud_risk":
        return _run_fraud(G, filters, limit)
    elif prediction_type == "demand_forecast":
        return _run_demand(G, filters, limit)
    else:
        # Unknown prediction type — fall back to churn
        return _run_churn(G, filters, limit)


def _run_churn(G: nx.DiGraph, filters: list[dict], limit: int) -> dict[str, Any]:
    """Score churn probability for all matching customers."""
    customer_nodes = [
        n for n, attrs in G.nodes(data=True)
        if attrs.get("node_type") == "customer"
        and _apply_filters(attrs, filters)
    ]

    scored: list[dict] = []
    all_traversal_steps: list[dict] = []

    for node in customer_nodes:
        attrs = G.nodes[node]
        signals, steps = collect_churn_signals(G, node)
        churn_score, confidence, top_factors = score_churn(signals)
        
        # Get prescriptive recovery action
        rec_action, success_prob = get_prescriptive_action(G, node, signals)

        if not all_traversal_steps and steps:
            # Only include traversal steps for the highest-risk customer (first after sort)
            # We'll swap these out after sorting below
            pass

        scored.append({
            "customer_id": attrs.get("customer_id", ""),
            "name": attrs.get("name", ""),
            "segment": attrs.get("segment", ""),
            "city": attrs.get("city", ""),
            "score": churn_score,
            "confidence": confidence,
            "top_factors": top_factors,
            "recommended_action": rec_action,
            "success_probability": success_prob,
            "_node": node,
            "_signals": signals,
            "_steps": steps,
        })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Attach traversal steps from the top-scored customer
    if scored:
        all_traversal_steps = scored[0].pop("_steps", [])
    for row in scored:
        row.pop("_node", None)
        row.pop("_signals", None)
        row.pop("_steps", None)

    total = len(scored)
    rows = scored[:limit]

    return {
        "query_type": "predictive",
        "results": rows,
        "traversal_steps": all_traversal_steps,
        "columns": ["name", "segment", "city", "score", "confidence", "top_factors", "recommended_action", "success_probability"],
        "total_results": total,
    }


def _run_purchase(G: nx.DiGraph, filters: list[dict], limit: int) -> dict[str, Any]:
    """Score purchase likelihood for all matching customers."""
    customer_nodes = [
        n for n, attrs in G.nodes(data=True)
        if attrs.get("node_type") == "customer"
        and _apply_filters(attrs, filters)
    ]

    scored: list[dict] = []

    for node in customer_nodes:
        attrs = G.nodes[node]
        signals, steps = collect_purchase_signals(G, node)
        p_score, confidence, top_factors = score_purchase_likelihood(signals)

        scored.append({
            "customer_id": attrs.get("customer_id", ""),
            "name": attrs.get("name", ""),
            "segment": attrs.get("segment", ""),
            "lifetime_value": attrs.get("lifetime_value", 0.0),
            "score": p_score,
            "confidence": confidence,
            "top_factors": top_factors,
            "_steps": steps,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    all_traversal_steps = scored[0].pop("_steps", []) if scored else []
    for row in scored:
        row.pop("_steps", None)

    total = len(scored)
    rows = scored[:limit]

    return {
        "query_type": "predictive",
        "results": rows,
        "traversal_steps": all_traversal_steps,
        "columns": ["name", "segment", "lifetime_value", "score", "confidence", "top_factors"],
        "total_results": total,
    }


def _run_fraud(G: nx.DiGraph, filters: list[dict], limit: int) -> dict[str, Any]:
    """Score fraud risk for all matching orders."""
    order_nodes = [
        n for n, attrs in G.nodes(data=True)
        if attrs.get("node_type") == "order"
        and _apply_filters(attrs, filters)
    ]

    scored: list[dict] = []

    for node in order_nodes:
        attrs = G.nodes[node]
        signals, steps = collect_fraud_signals(G, node)
        f_score, confidence, top_factors = score_fraud_risk(signals)

        # Find customer name
        customer_node = next(
            (n for n in G.predecessors(node) if G.nodes[n].get("node_type") == "customer"),
            None,
        )
        customer_name = G.nodes[customer_node].get("name", "Unknown") if customer_node else "Unknown"

        scored.append({
            "order_id": attrs.get("order_id", ""),
            "customer_name": customer_name,
            "order_date": attrs.get("order_date", ""),
            "total_amount": attrs.get("total_amount", 0.0),
            "status": attrs.get("status", ""),
            "score": f_score,
            "confidence": confidence,
            "top_factors": top_factors,
            "_steps": steps,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)

    all_traversal_steps = scored[0].pop("_steps", []) if scored else []
    for row in scored:
        row.pop("_steps", None)

    total = len(scored)
    rows = scored[:limit]

    return {
        "query_type": "predictive",
        "results": rows,
        "traversal_steps": all_traversal_steps,
        "columns": ["order_id", "customer_name", "order_date", "total_amount", "score", "confidence", "top_factors"],
        "total_results": total,
    }


def _run_demand(G: nx.DiGraph, filters: list[dict], limit: int) -> dict[str, Any]:
    """Forecast demand by product category."""
    categories = list({
        attrs.get("category", "")
        for _, attrs in G.nodes(data=True)
        if attrs.get("node_type") == "product" and attrs.get("category")
    })

    rows: list[dict] = []
    all_traversal_steps: list[dict] = []

    for category in sorted(categories):
        signals, steps = collect_demand_signals(G, category)
        predicted_units, predicted_revenue, confidence = score_demand(signals)

        if not all_traversal_steps and steps:
            all_traversal_steps = steps

        rows.append({
            "category": category,
            "predicted_units": predicted_units,
            "predicted_revenue": predicted_revenue,
            "confidence": confidence,
            "total_units_sold": signals.get("total_units_sold", 0),
            "total_revenue": round(signals.get("total_revenue", 0.0), 2),
        })

    rows.sort(key=lambda x: x["predicted_revenue"], reverse=True)

    return {
        "query_type": "predictive",
        "results": rows[:limit],
        "traversal_steps": all_traversal_steps,
        "columns": ["category", "predicted_units", "predicted_revenue", "confidence", "total_units_sold"],
        "total_results": len(rows),
    }
