"""
PQL execution engine.

All queries run against KumoRFM + cached users/items/orders (see ``rfm`` package).
"""

from __future__ import annotations

from typing import Any

from pql.parser import parse_pql
from rfm.cache import RFMBundle


def execute(pql_query: str, rfm_bundle: RFMBundle) -> dict[str, Any]:
    """
    Parse and execute PQL against the KumoRFM bundle.

    Returns a dict with:
      - query_type: "factual" | "predictive"
      - results: list of row dicts
      - traversal_steps: list of step dicts
      - columns: list of column names for the result table
      - total_results: int (before LIMIT)
    """
    plan = parse_pql(pql_query)

    if plan["mode"] == "factual":
        from rfm.factual import run_factual

        return run_factual(rfm_bundle, plan)

    from rfm.predict import run_predictive

    return run_predictive(rfm_bundle, plan)
