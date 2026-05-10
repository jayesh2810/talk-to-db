"""
PQL execution engine backed by KumoRFM.

Routes parsed PQL plans to either:
  - Factual: pandas DataFrame query (SELECT-style)
  - Predictive: KumoRFM model.predict() call
"""

from __future__ import annotations

import traceback
from typing import Any

import pandas as pd

from kumo_rfm.client import predict, get_dataframes


def execute(pql_query: str, plan: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a PQL query using the appropriate backend.

    For factual queries: runs pandas filter/sort/limit on cached DataFrames.
    For predictive queries: passes the PQL string to KumoRFM model.predict().

    Returns a dict with:
      - query_type: "factual" | "predictive"
      - results: list of row dicts
      - columns: list of column names
      - total_results: int
    """
    if plan["mode"] == "factual":
        return _execute_factual(plan)
    else:
        return _execute_predictive(pql_query, plan)


def _execute_factual(plan: dict[str, Any]) -> dict[str, Any]:
    """Run a factual lookup against the cached pandas DataFrames."""
    dfs = get_dataframes()
    table = plan.get("table", "")

    if table not in dfs:
        for name in dfs:
            if table in name or name in table:
                table = name
                break
        else:
            table = list(dfs.keys())[0]

    df = dfs[table].copy()

    for f in plan.get("filters", []):
        col = f["field"]
        if col not in df.columns:
            continue
        op = f["op"]
        val = f["value"]
        if op == "=":
            df = df[df[col] == val]
        elif op == "!=":
            df = df[df[col] != val]
        elif op == ">":
            df = df[pd.to_numeric(df[col], errors="coerce") > float(val)]
        elif op == "<":
            df = df[pd.to_numeric(df[col], errors="coerce") < float(val)]
        elif op == ">=":
            df = df[pd.to_numeric(df[col], errors="coerce") >= float(val)]
        elif op == "<=":
            df = df[pd.to_numeric(df[col], errors="coerce") <= float(val)]

    order_by = plan.get("order_by")
    order_dir = plan.get("order_dir", "DESC")
    if order_by and order_by in df.columns:
        df = df.sort_values(order_by, ascending=(order_dir == "ASC"))

    total = len(df)
    limit = plan.get("limit", 50)
    df = df.head(limit)

    return_fields = plan.get("return_fields", [])
    if return_fields:
        valid = [c for c in return_fields if c in df.columns]
        if valid:
            df = df[valid]

    for col in df.columns:
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].fillna(0)
        elif pd.api.types.is_float_dtype(df[col]):
            df[col] = df[col].fillna(0.0)
        else:
            df[col] = df[col].fillna("")
    rows = df.to_dict(orient="records")
    columns = list(df.columns)

    return {
        "query_type": "factual",
        "results": rows,
        "columns": columns,
        "total_results": total,
    }


def _execute_predictive(pql_query: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Run a predictive query through KumoRFM model.predict()."""
    try:
        indices = plan.get("indices")
        result_df = predict(pql_query, indices=indices)

        if isinstance(result_df, pd.DataFrame):
            rows = result_df.head(50).to_dict(orient="records")
            columns = list(result_df.columns)
            total = len(result_df)
        else:
            rows = [{"prediction": str(result_df)}]
            columns = ["prediction"]
            total = 1

        # Round numeric values for readability
        for row in rows:
            for key, val in row.items():
                if isinstance(val, float):
                    row[key] = round(val, 4)

        return {
            "query_type": "predictive",
            "results": rows,
            "columns": columns,
            "total_results": total,
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "query_type": "predictive",
            "results": [{"error": str(e)}],
            "columns": ["error"],
            "total_results": 0,
        }
