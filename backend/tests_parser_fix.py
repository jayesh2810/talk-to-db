"""
End-to-end tests for the parser/executor fix.

Covers:
  1. Parser unit tests across factual, predictive, edge cases.
  2. run_factual against a synthetic in-memory RFMBundle.
  3. run_predictive with a fake KumoRFM model, asserting the correct
     PQL string + indices + branch are chosen.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# Allow `import pql.parser` when run as a script
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pql.parser import parse_pql  # noqa: E402
from rfm.cache import RFMBundle  # noqa: E402
from rfm.factual import run_factual  # noqa: E402
from rfm.predict import run_predictive  # noqa: E402


PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((PASS if cond else FAIL, name, detail))
    marker = "+" if cond else "X"
    print(f"  [{marker}] {name}" + (f"  -- {detail}" if detail and not cond else ""))


# ─── 1. Parser unit tests ───────────────────────────────────────────────

def test_parser() -> None:
    print("\n[1] Parser output")

    # Factual: items table preserved, filter extracted
    p = parse_pql("MATCH items WHERE category = 'Trousers' RETURN item_id, item_name LIMIT 15")
    check("factual items: table=items", p["table"] == "items", repr(p))
    check("factual items: entity_type=product", p["entity_type"] == "product", repr(p))
    check("factual items: filter on category",
          p["filters"] == [{"field": "category", "op": "=", "value": "Trousers"}], repr(p))
    check("factual items: return fields", p["return_fields"] == ["item_id", "item_name"])
    check("factual items: limit=15", p["limit"] == 15)

    # Factual: orders
    p = parse_pql("MATCH orders WHERE price > 100 RETURN order_id, price LIMIT 5")
    check("factual orders: table=orders", p["table"] == "orders")
    check("factual orders: entity_type=order", p["entity_type"] == "order")
    check("factual orders: numeric filter",
          p["filters"] == [{"field": "price", "op": ">", "value": 100}], repr(p["filters"]))

    # Factual: customer alias still maps to users
    p = parse_pql("MATCH customer WHERE active = true RETURN user_id LIMIT 3")
    check("factual customer: table=users", p["table"] == "users")
    check("factual customer: entity_type=customer", p["entity_type"] == "customer")

    # Predictive: churn
    p = parse_pql("PREDICT churn_probability FOR EACH customer USING orders HORIZON 60 days "
                  "RETURN score ORDER BY score DESC LIMIT 20")
    check("predict churn: prediction_type", p["prediction_type"] == "churn_probability")
    check("predict churn: entity_type=customer", p["entity_type"] == "customer")
    check("predict churn: horizon_days=60", p["horizon_days"] == 60, repr(p))
    check("predict churn: limit=20", p["limit"] == 20)
    check("predict churn: no spurious WHERE filters", p["filters"] == [], repr(p["filters"]))

    # Predictive: demand_forecast for product
    p = parse_pql("PREDICT demand_forecast FOR EACH product USING orders, items HORIZON 30 days "
                  "RETURN category, score LIMIT 15")
    check("predict demand: prediction_type", p["prediction_type"] == "demand_forecast")
    check("predict demand: entity_type=product", p["entity_type"] == "product")
    check("predict demand: horizon_days=30", p["horizon_days"] == 30)

    # Predictive: purchase_likelihood with WHERE
    p = parse_pql("PREDICT purchase_likelihood FOR EACH customer "
                  "WHERE active = true HORIZON 45 days RETURN score LIMIT 10")
    check("predict purchase: prediction_type", p["prediction_type"] == "purchase_likelihood")
    check("predict purchase: WHERE extracted",
          p["filters"] == [{"field": "active", "op": "=", "value": "true"}], repr(p["filters"]))
    check("predict purchase: horizon=45 (not polluted by WHERE)", p["horizon_days"] == 45)

    # Edge: HORIZON in weeks/months
    p = parse_pql("PREDICT churn_probability FOR EACH user HORIZON 2 weeks RETURN score LIMIT 5")
    check("predict weeks->14 days", p["horizon_days"] == 14)
    p = parse_pql("PREDICT churn_probability FOR EACH user HORIZON 3 months RETURN score LIMIT 5")
    check("predict months->90 days", p["horizon_days"] == 90)

    # Edge: dotted entity spec (`users.user_id`)
    p = parse_pql("PREDICT churn_probability FOR EACH users.user_id HORIZON 30 days LIMIT 5")
    check("predict dotted: entity_table=users", p["entity_table"] == "users")
    check("predict dotted: entity_type=customer", p["entity_type"] == "customer")

    # Edge: IN (...) indices
    p = parse_pql("PREDICT churn_probability FOR EACH users.user_id IN (1, 2, 3) "
                  "HORIZON 30 days LIMIT 5")
    check("predict IN(): indices parsed", p["indices"] == [1, 2, 3], repr(p["indices"]))

    # Edge: missing HORIZON → default 90
    p = parse_pql("PREDICT churn_probability FOR EACH customer RETURN score LIMIT 5")
    check("predict no horizon: default 90", p["horizon_days"] == 90)

    # Edge: missing LIMIT → default 20
    p = parse_pql("PREDICT churn_probability FOR EACH customer HORIZON 30 days")
    check("predict no limit: default 20", p["limit"] == 20)

    # Edge: unknown predict target falls back to its lowered string (not silently churn)
    p = parse_pql("PREDICT something_weird FOR EACH customer HORIZON 30 days LIMIT 5")
    check("predict unknown target: not silently churn",
          p["prediction_type"] == "something_weird", repr(p["prediction_type"]))


# ─── 2. Factual end-to-end with synthetic bundle ────────────────────────

def synthetic_bundle() -> RFMBundle:
    users = pd.DataFrame({
        "user_id": [1, 2, 3, 4],
        "age": [25, 42, 31, 67],
        "active": [True, False, True, True],
    })
    items = pd.DataFrame({
        "item_id": [10, 11, 12, 13],
        "item_name": ["Jeans", "Tee", "Hat", "Boots"],
        "category": ["Trousers", "Tops", "Hats", "Trousers"],
    })
    orders = pd.DataFrame({
        "order_id": [100, 101, 102, 103, 104],
        "user_id": [1, 1, 2, 3, 4],
        "item_id": [10, 11, 12, 13, 10],
        "price": [80.0, 25.0, 15.0, 120.0, 80.0],
        "date": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01", "2026-03-15", "2026-04-01"]),
    })
    return RFMBundle(graph=None, model=None, users=users, items=items, orders=orders)


def test_factual_executor() -> None:
    print("\n[2] Factual executor (synthetic data)")
    bundle = synthetic_bundle()

    # ITEMS query: previously returned USERS rows due to default entity_type
    plan = parse_pql("MATCH items WHERE category = 'Trousers' RETURN item_id, item_name LIMIT 15")
    out = run_factual(bundle, plan)
    item_ids = sorted(r["item_id"] for r in out["results"])
    check("items WHERE Trousers: returns 2 item rows",
          len(out["results"]) == 2 and item_ids == [10, 13], repr(out["results"]))
    check("items query: columns are item fields",
          out["columns"] == ["item_id", "item_name"], repr(out["columns"]))

    # ORDERS query
    plan = parse_pql("MATCH orders WHERE price > 50 RETURN order_id, price LIMIT 10")
    out = run_factual(bundle, plan)
    order_ids = sorted(r["order_id"] for r in out["results"])
    check("orders WHERE price>50: 3 rows",
          len(out["results"]) == 3 and order_ids == [100, 103, 104], repr(out["results"]))

    # USERS query (regression: must still work)
    plan = parse_pql("MATCH customer WHERE active = true RETURN user_id, age LIMIT 10")
    out = run_factual(bundle, plan)
    ids = sorted(r["user_id"] for r in out["results"])
    check("customers active=true: 3 rows", ids == [1, 3, 4], repr(out["results"]))

    # Empty result set
    plan = parse_pql("MATCH items WHERE category = 'NoSuch' RETURN item_id LIMIT 5")
    out = run_factual(bundle, plan)
    check("empty result: 0 rows", out["results"] == [] and out["total_results"] == 0)

    # Order by + ascending
    plan = parse_pql("MATCH customer RETURN user_id, age ORDER BY age ASC LIMIT 10")
    out = run_factual(bundle, plan)
    ages = [r["age"] for r in out["results"]]
    check("order by age ASC: monotonic non-decreasing", ages == sorted(ages), repr(ages))

    # Limit larger than dataset still returns all
    plan = parse_pql("MATCH items RETURN item_id LIMIT 1000")
    out = run_factual(bundle, plan)
    check("limit > dataset: returns all 4 items",
          len(out["results"]) == 4, repr(out["results"]))


# ─── 3. Predictive executor with mocked Kumo model ──────────────────────

@dataclass
class _Captured:
    queries: list[str]
    indices_list: list[list[Any]]


class _FakeModel:
    """Records calls; returns a deterministic DataFrame so the executor can rank rows."""

    def __init__(self) -> None:
        self.captured = _Captured(queries=[], indices_list=[])

    @contextmanager
    def batch_mode(self, **kwargs: Any):  # type: ignore[no-untyped-def]
        del kwargs
        yield

    def predict(self, query: str, *, indices: list[Any], run_mode: str = "fast") -> pd.DataFrame:
        del run_mode
        self.captured.queries.append(query)
        self.captured.indices_list.append(list(indices))
        # Pretend probabilities; vary by index so ordering is non-trivial
        return pd.DataFrame({
            "ENTITY": indices,
            "True_PROB": [0.1 + 0.2 * i for i in range(len(indices))],
            "TARGET_PRED": [float(i + 1) * 10.0 for i in range(len(indices))],
        })


def test_predictive_executor() -> None:
    print("\n[3] Predictive executor (fake Kumo model)")
    bundle = synthetic_bundle()
    bundle = RFMBundle(graph=None, model=_FakeModel(), users=bundle.users,
                       items=bundle.items, orders=bundle.orders)
    fake: _FakeModel = bundle.model  # type: ignore[assignment]

    # 3a. CHURN for customer, horizon=60 → user-centric path, churn PQL with 60 days
    plan = parse_pql("PREDICT churn_probability FOR EACH customer "
                     "USING orders HORIZON 60 days RETURN score ORDER BY score DESC LIMIT 20")
    out = run_predictive(bundle, plan)
    last_q = fake.captured.queries[-1]
    check("churn: routed to user-centric path",
          all("user_id" in r for r in out["results"]), repr(out["columns"]))
    check("churn: PQL uses COUNT(orders.*, 0, 60, days)=0",
          "COUNT(orders.*, 0, 60, days)=0" in last_q, last_q)
    check("churn: indices are all users", sorted(fake.captured.indices_list[-1]) == [1, 2, 3, 4])

    # 3b. PURCHASE_LIKELIHOOD with WHERE active=true, horizon=45 → only active users indexed
    plan = parse_pql("PREDICT purchase_likelihood FOR EACH customer "
                     "WHERE active = true HORIZON 45 days RETURN score LIMIT 10")
    out = run_predictive(bundle, plan)
    last_q = fake.captured.queries[-1]
    check("purchase: PQL uses COUNT(...) > 0 with 45 days",
          "COUNT(orders.*, 0, 45, days) > 0" in last_q, last_q)
    check("purchase: WHERE active=true filtered indices to 3 users",
          sorted(fake.captured.indices_list[-1]) == [1, 3, 4],
          repr(fake.captured.indices_list[-1]))

    # 3c. DEMAND_FORECAST for product, horizon=30 → item-centric, SUM PQL
    plan = parse_pql("PREDICT demand_forecast FOR EACH product USING orders, items "
                     "HORIZON 30 days RETURN category, score LIMIT 15")
    out = run_predictive(bundle, plan)
    last_q = fake.captured.queries[-1]
    check("demand: routed to item-centric path",
          out["columns"][:2] == ["category", "item_id"], repr(out["columns"]))
    check("demand: PQL uses SUM(orders.price, 0, 30, days)",
          "SUM(orders.price, 0, 30, days)" in last_q, last_q)
    check("demand: indices are item ids",
          sorted(fake.captured.indices_list[-1]) == [10, 11, 12, 13])

    # 3d. fraud_risk should raise (unsupported on this dataset)
    plan = parse_pql("PREDICT fraud_risk FOR EACH customer HORIZON 30 days LIMIT 5")
    raised = False
    try:
        run_predictive(bundle, plan)
    except ValueError:
        raised = True
    check("fraud_risk: raises ValueError", raised)

    # 3e. Empty user filter → empty result, no model call
    bundle.users = bundle.users.iloc[0:0].copy()
    fake.captured.queries.clear()
    fake.captured.indices_list.clear()
    plan = parse_pql("PREDICT churn_probability FOR EACH customer HORIZON 30 days LIMIT 5")
    out = run_predictive(bundle, plan)
    check("empty users: no model.predict call", fake.captured.queries == [])
    check("empty users: empty results", out["results"] == [] and out["total_results"] == 0)


# ─── Run all ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_parser()
    test_factual_executor()
    test_predictive_executor()
    fails = [r for r in results if r[0] == FAIL]
    passes = [r for r in results if r[0] == PASS]
    print(f"\nSummary: {len(passes)} passed, {len(fails)} failed (total {len(results)})")
    if fails:
        for _, name, detail in fails:
            print(f"  FAIL: {name}  -- {detail}")
        sys.exit(1)
    sys.exit(0)
