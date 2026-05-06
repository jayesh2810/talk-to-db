"""User detail view backed by Kumo online-shopping tables + optional churn score."""

from __future__ import annotations

from typing import Any

import pandas as pd

from rfm.cache import RFMBundle
from rfm.predict import _optional_bool, _sanitize, churn_score_for_user


def build_user_profile(bundle: RFMBundle, user_id: str) -> dict[str, Any]:
    try:
        uid = int(user_id.strip())
    except ValueError as e:
        raise ValueError("user_id must be an integer") from e

    umatch = bundle.users[bundle.users["user_id"] == uid]
    if umatch.empty:
        raise ValueError("User not found")

    active = _optional_bool(umatch["active"].iloc[0])
    age = umatch["age"].iloc[0]
    try:
        age_i = int(age) if pd.notna(age) else None
    except (TypeError, ValueError):
        age_i = None

    seg = "unknown"
    if active is True:
        seg = "active"
    elif active is False:
        seg = "inactive"

    orders_df = bundle.orders[bundle.orders["user_id"] == uid].copy()
    merged = orders_df.merge(
        bundle.items[["item_id", "item_name", "category"]],
        on="item_id",
        how="left",
    )
    merged.sort_values("date", ascending=False, inplace=True)

    order_rows: list[dict[str, Any]] = []
    for _, r in merged.iterrows():
        price = float(r.get("price") or 0)
        order_rows.append(
            {
                "order_id": str(r.get("order_id", "")),
                "order_date": str(r.get("date", "")),
                "total_amount": round(price, 2),
                "status": "completed",
                "delivery_days": 0,
                "promised_days": 0,
                "items": [
                    {
                        "product_name": str(r.get("item_name", "")),
                        "category": str(r.get("category", "")),
                        "quantity": 1,
                        "unit_price": round(price, 2),
                        "returned": False,
                    }
                ],
            }
        )

    lifetime = float(orders_df["price"].sum()) if "price" in orders_df.columns else 0.0

    try:
        score, confidence, factors = churn_score_for_user(bundle, uid)
    except Exception:
        score, confidence, factors = 0.0, 0.0, []

    raw_signals = {
        "user_id": uid,
        "active": active,
        "age": age_i,
        "order_rows": int(len(orders_df)),
        "lifetime_spend_kumo": round(lifetime, 2),
    }

    return _sanitize(
        {
            "profile": {
                "id": str(uid),
                "name": f"user_{uid}",
                "segment": seg,
                "city": "",
                "lifetime_value": round(lifetime, 2),
                "signup_date": "",
                "acq_channel": "",
                "age": age_i,
            },
            "orders": order_rows,
            "churn": {
                "score": score,
                "confidence": confidence,
                "top_factors": factors,
                "raw_signals": raw_signals,
            },
        }
    )
