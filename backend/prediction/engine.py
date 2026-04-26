"""
Weighted deterministic scoring engine.

Each scoring function takes a signals dict (from traversal.py) and returns:
  (score: float, confidence: float, top_factors: list[dict])

Scores are in [0, 1]. Same input always produces same output.
"""

from typing import Any

from prediction.signals import (
    normalize_days,
    normalize_rate,
    normalize_count,
    invert,
    clamp,
    variance_confidence,
)


def score_churn(
    signals: dict[str, Any], *, sql_mode: bool = False
) -> tuple[float, float, list[dict]]:
    """
    Score churn probability for a customer.

    High score (→ 1.0) = high churn risk.
    Low score (→ 0.0) = low churn risk.

    Weights reflect empirical importance from retention research:
      - Recency is the strongest single predictor
      - Multi-hop peer signal captures social/category-level churn contagion

    When sql_mode=True, the graph-derived peer_churn_rate is excluded and remaining
    weights are renormalized (SQL-style baseline for comparison with graph scores).
    """
    weights: dict[str, float] = {
        "days_since_last_order":     0.28,
        "return_rate":               0.20,
        "negative_interaction_rate": 0.18,
        "campaign_open_rate":        0.15,  # inverted: low open rate → high risk
        "peer_churn_rate":           0.12,
        "unresolved_issues":         0.07,
    }
    if sql_mode:
        weights.pop("peer_churn_rate", None)
        wsum = sum(weights.values())
        weights = {k: v / wsum for k, v in weights.items()}

    normalized = {
        "days_since_last_order":     normalize_days(signals.get("days_since_last_order", 0), max_days=90),
        "return_rate":               normalize_rate(signals.get("return_rate", 0.0)),
        "negative_interaction_rate": normalize_rate(signals.get("negative_interaction_rate", 0.0)),
        "campaign_open_rate":        invert(signals.get("campaign_open_rate", 0.5)),
        "peer_churn_rate":           normalize_rate(signals.get("peer_churn_rate", 0.0)),
        "unresolved_issues":         normalize_count(signals.get("unresolved_issues", 0), max_count=3),
    }

    score = clamp(sum(normalized[k] * weights[k] for k in weights))

    signal_values = [normalized[k] for k in weights]
    confidence = variance_confidence(signal_values, score)

    # Reduce confidence for customers with very few data points
    if signals.get("total_orders", 0) < 2:
        confidence *= 0.6
    confidence = clamp(confidence)

    contributions = {k: normalized[k] * weights[k] for k in weights}
    top_factors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
    top_factors_list = [
        {
            "factor": k,
            "contribution": round(v, 3),
            "raw_value": signals.get(k),
        }
        for k, v in top_factors
    ]

    return round(score, 3), round(confidence, 3), top_factors_list


def score_purchase_likelihood(signals: dict[str, Any]) -> tuple[float, float, list[dict]]:
    """
    Score purchase likelihood for a customer in the next 30 days.

    High score (→ 1.0) = very likely to purchase.
    """
    weights = {
        "days_since_last_order":    0.30,  # inverted: recent order → likely to buy
        "campaign_conversion_rate": 0.25,
        "peer_recent_purchase_rate": 0.20,
        "category_diversity":       0.15,
        "positive_sentiment_rate":  0.10,
    }

    max_gap = signals.get("avg_order_gap_days", 90) or 90
    # If last order was recent relative to their typical gap, purchase is likely
    recency_score = invert(normalize_days(signals.get("days_since_last_order", 90), max_days=max_gap))

    normalized = {
        "days_since_last_order":     recency_score,
        "campaign_conversion_rate":  normalize_rate(signals.get("campaign_conversion_rate", 0.0)),
        "peer_recent_purchase_rate": normalize_rate(signals.get("peer_recent_purchase_rate", 0.0)),
        "category_diversity":        normalize_count(signals.get("category_diversity", 0), max_count=6),
        "positive_sentiment_rate":   normalize_rate(signals.get("positive_sentiment_rate", 0.5)),
    }

    score = clamp(sum(normalized[k] * weights[k] for k in weights))
    confidence = variance_confidence(list(normalized.values()), score)

    if signals.get("total_orders", 0) < 2:
        confidence *= 0.6
    confidence = clamp(confidence)

    contributions = {k: normalized[k] * weights[k] for k in weights}
    top_factors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
    top_factors_list = [
        {"factor": k, "contribution": round(v, 3), "raw_value": signals.get(k)}
        for k, v in top_factors
    ]

    return round(score, 3), round(confidence, 3), top_factors_list


def score_fraud_risk(signals: dict[str, Any]) -> tuple[float, float, list[dict]]:
    """
    Score fraud risk for a specific order.

    High score (→ 1.0) = high fraud risk.
    Key signal: new account + high-value order + rapid order velocity.
    """
    weights = {
        "new_account_factor":    0.30,
        "high_value_factor":     0.25,
        "order_velocity_factor": 0.20,
        "immediate_return":      0.15,
        "no_campaign_engagement": 0.10,
    }

    account_age = signals.get("account_age_days", 999)
    normalized = {
        "new_account_factor":    invert(normalize_days(account_age, max_days=30)),
        "high_value_factor":     normalize_count(int(signals.get("order_amount", 0)), max_count=500),
        "order_velocity_factor": normalize_count(signals.get("order_velocity_3d", 1), max_count=4),
        "immediate_return":      1.0 if signals.get("immediate_return") else 0.0,
        "no_campaign_engagement": invert(normalize_rate(signals.get("campaign_engagement", 0.5))),
    }

    score = clamp(sum(normalized[k] * weights[k] for k in weights))
    confidence = variance_confidence(list(normalized.values()), score)
    confidence = clamp(confidence)

    contributions = {k: normalized[k] * weights[k] for k in weights}
    top_factors = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
    top_factors_list = [
        {"factor": k, "contribution": round(v, 3), "raw_value": signals.get(k)}
        for k, v in top_factors
    ]

    return round(score, 3), round(confidence, 3), top_factors_list


def score_demand(signals: dict[str, Any]) -> tuple[float, float, float]:
    """
    Produce demand forecast for a product category.

    Returns:
        predicted_units: extrapolated units for the horizon period
        predicted_revenue: extrapolated revenue
        confidence: based on data volume
    """
    units_30d = signals.get("units_30d", 0)
    units_60d = signals.get("units_60d", 0)
    total = signals.get("total_units_sold", 0)
    revenue = signals.get("total_revenue", 0.0)

    # Simple linear trend: compare 0-30d vs 30-60d window
    units_30_60d = units_60d - units_30d
    if units_30_60d > 0:
        trend_factor = units_30d / units_30_60d
    else:
        trend_factor = 1.0

    # Forecast next 90 days based on trend
    predicted_units = round(units_30d * 3 * min(trend_factor, 2.0))
    avg_unit_revenue = (revenue / total) if total > 0 else 0.0
    predicted_revenue = round(predicted_units * avg_unit_revenue, 2)

    confidence = clamp(normalize_count(total, max_count=50))
    return predicted_units, predicted_revenue, round(confidence, 3)
