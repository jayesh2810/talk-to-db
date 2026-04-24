"""
Multi-hop graph traversal for predictive signal collection.

This is the architectural core of the system. For each entity being scored,
we traverse multiple hops in the graph to collect signals that flat SQL joins
cannot capture — most importantly the *peer customer* signal:

  customer → orders → products → other customers (who bought the same products)

If those peer customers are also becoming inactive, it amplifies the original
customer's churn risk. This collaborative signal mirrors what Kumo.ai's
relational foundation models learn from graph structure.
"""

import datetime
from typing import Any

import networkx as nx

_TODAY = datetime.date.today()


# ─── Type-safe attribute accessors ───────────────────────────────────────────

def _float(attrs: dict, key: str, default: float = 0.0) -> float:
    val = attrs.get(key, default)
    if val == "" or val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _int(attrs: dict, key: str, default: int = 0) -> int:
    val = attrs.get(key, default)
    if val == "" or val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _bool(attrs: dict, key: str, default: bool = False) -> bool:
    val = attrs.get(key, default)
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return bool(val)


def _str(attrs: dict, key: str, default: str = "") -> str:
    val = attrs.get(key, default)
    return str(val) if val is not None and val != "" else default


def _days_ago(date_str: str) -> int:
    """Return number of days between today and a given ISO date string."""
    if not date_str:
        return 9999
    try:
        d = datetime.date.fromisoformat(date_str)
        return (_TODAY - d).days
    except ValueError:
        return 9999


def _successors_of_type(G: nx.DiGraph, node: str, node_type: str) -> list[str]:
    return [n for n in G.successors(node) if _str(G.nodes[n], "node_type") == node_type]


# ─── Churn signal collection ──────────────────────────────────────────────────

def collect_churn_signals(
    G: nx.DiGraph,
    customer_node: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Traverse the graph to collect churn-predictive signals for a customer.

    Returns:
        signals: dict of raw signal values for the scoring engine
        steps: list of traversal step dicts for the interpretability layer
    """
    signals: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    step_num = 0

    # ── Hop 1a: customer → orders ─────────────────────────────────────────────
    order_nodes = _successors_of_type(G, customer_node, "order")
    orders = [G.nodes[n] for n in order_nodes]
    completed = [o for o in orders if _str(o, "status") == "completed"]
    returned = [o for o in orders if _str(o, "status") == "returned"]

    signals["total_orders"] = len(completed)
    signals["return_rate"] = len(returned) / max(len(orders), 1)

    if completed:
        dates = sorted([_str(o, "order_date") for o in completed])
        signals["days_since_last_order"] = _days_ago(dates[-1])
        signals["avg_order_value"] = sum(_float(o, "total_amount") for o in completed) / len(completed)
    else:
        signals["days_since_last_order"] = 180
        signals["avg_order_value"] = 0.0

    # Late delivery rate
    late = sum(
        1 for o in orders
        if _int(o, "delivery_days") > _int(o, "promised_days") and _str(o, "status") == "completed"
    )
    signals["late_delivery_rate"] = late / max(len(orders), 1)

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(order_nodes)} orders for {customer_node}",
        "detail": (
            f"days_since_last_order={signals['days_since_last_order']}, "
            f"return_rate={signals['return_rate']:.2f}, "
            f"avg_order_value=${signals['avg_order_value']:.2f}"
        ),
    })

    # ── Hop 2: orders → products ──────────────────────────────────────────────
    product_nodes: list[str] = []
    for order_node in order_nodes:
        product_nodes += _successors_of_type(G, order_node, "product")

    categories = [_str(G.nodes[p], "category") for p in product_nodes]
    signals["category_diversity"] = len(set(categories))

    category_counts: dict[str, int] = {}
    for cat in categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1
    cat_detail = ", ".join(f"{k}({v})" for k, v in sorted(category_counts.items(), key=lambda x: -x[1]))

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 2,
        "description": f"Traversed orders → products ({len(product_nodes)} products across {signals['category_diversity']} categories)",
        "detail": f"categories: {cat_detail}" if cat_detail else "no products found",
    })

    # ── Hop 3: products → peer customers (the multi-hop signal) ───────────────
    peer_nodes: set[str] = set()
    for product_node in product_nodes:
        for n in G.successors(product_node):
            if _str(G.nodes[n], "node_type") == "customer" and n != customer_node:
                peer_nodes.add(n)

    peer_churn_indicators: list[int] = []
    sampled_peers = list(peer_nodes)[:12]  # cap for performance

    for peer_node in sampled_peers:
        peer_order_nodes = _successors_of_type(G, peer_node, "order")
        peer_completed = [
            _str(G.nodes[n], "order_date")
            for n in peer_order_nodes
            if _str(G.nodes[n], "status") == "completed"
        ]
        if peer_completed:
            last_date = max(peer_completed)
            peer_churn_indicators.append(1 if _days_ago(last_date) > 60 else 0)

    peer_churn_rate = sum(peer_churn_indicators) / max(len(peer_churn_indicators), 1) if peer_churn_indicators else 0.0
    signals["peer_churn_rate"] = peer_churn_rate

    inactive_peers = sum(peer_churn_indicators)
    peer_detail = (
        f"peer_churn_rate={peer_churn_rate:.2f} — "
        + (
            f"{inactive_peers} of {len(sampled_peers)} peer customers also showing inactivity"
            if sampled_peers
            else "no peer customers found"
        )
    )

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 3,
        "description": f"Traversed products → peer customers ({len(peer_nodes)} peers who bought same products)",
        "detail": peer_detail,
    })

    # ── Hop 1b: customer → interactions ──────────────────────────────────────
    interaction_nodes = _successors_of_type(G, customer_node, "interaction")
    interactions = [G.nodes[n] for n in interaction_nodes]
    sentiments = [_str(i, "sentiment") for i in interactions]
    topics = [_str(i, "topic") for i in interactions]

    signals["negative_interaction_rate"] = sentiments.count("negative") / max(len(sentiments), 1)
    signals["unresolved_issues"] = sum(1 for i in interactions if not _bool(i, "resolved"))
    signals["total_interactions"] = len(interactions)

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(interaction_nodes)} support interactions",
        "detail": (
            f"negative={sentiments.count('negative')}, "
            f"positive={sentiments.count('positive')}, "
            f"unresolved={signals['unresolved_issues']}, "
            f"topics: {', '.join(set(topics)) or 'none'}"
        ),
    })

    # ── Hop 1c: customer → campaign touchpoints ───────────────────────────────
    campaign_nodes = _successors_of_type(G, customer_node, "campaign")
    campaigns = [G.nodes[n] for n in campaign_nodes]

    if campaigns:
        signals["campaign_open_rate"] = sum(1 for c in campaigns if _bool(c, "opened")) / len(campaigns)
        signals["campaign_click_rate"] = sum(1 for c in campaigns if _bool(c, "clicked")) / len(campaigns)
        signals["campaign_conversion_rate"] = sum(1 for c in campaigns if _bool(c, "converted")) / len(campaigns)
    else:
        signals["campaign_open_rate"] = 0.0
        signals["campaign_click_rate"] = 0.0
        signals["campaign_conversion_rate"] = 0.0

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(campaign_nodes)} campaign touchpoints",
        "detail": (
            f"open_rate={signals['campaign_open_rate']:.2f}, "
            f"conversion_rate={signals['campaign_conversion_rate']:.2f}"
            + (
                " — disengaged from marketing"
                if signals["campaign_open_rate"] < 0.25
                else " — actively engaging"
            )
        ),
    })

    return signals, steps


# ─── Purchase likelihood signal collection ───────────────────────────────────

def collect_purchase_signals(
    G: nx.DiGraph,
    customer_node: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Collect signals predicting whether a customer will make a purchase."""
    signals: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    step_num = 0

    # Hop 1: Order recency & frequency
    order_nodes = _successors_of_type(G, customer_node, "order")
    completed_orders = [
        G.nodes[n] for n in order_nodes
        if _str(G.nodes[n], "status") == "completed"
    ]
    signals["total_orders"] = len(completed_orders)

    if completed_orders:
        dates = sorted([_str(o, "order_date") for o in completed_orders])
        signals["days_since_last_order"] = _days_ago(dates[-1])

        if len(dates) >= 2:
            gaps = [
                (_days_ago(dates[i]) - _days_ago(dates[i + 1]))
                for i in range(len(dates) - 1)
            ]
            signals["avg_order_gap_days"] = sum(gaps) / len(gaps)
        else:
            signals["avg_order_gap_days"] = 90
    else:
        signals["days_since_last_order"] = 180
        signals["avg_order_gap_days"] = 180

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(order_nodes)} orders for {customer_node}",
        "detail": (
            f"days_since_last_order={signals['days_since_last_order']}, "
            f"avg_gap_days={signals.get('avg_order_gap_days', 0):.0f}"
        ),
    })

    # Hop 2: Product categories purchased
    product_nodes: list[str] = []
    for order_node in order_nodes:
        product_nodes += _successors_of_type(G, order_node, "product")

    signals["category_diversity"] = len(set(_str(G.nodes[p], "category") for p in product_nodes))

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 2,
        "description": f"Traversed orders → products ({len(product_nodes)} products)",
        "detail": f"category_diversity={signals['category_diversity']}",
    })

    # Hop 3: Peer customers' recent activity
    peer_nodes: set[str] = set()
    for product_node in product_nodes:
        for n in G.successors(product_node):
            if _str(G.nodes[n], "node_type") == "customer" and n != customer_node:
                peer_nodes.add(n)

    peer_active = []
    for peer_node in list(peer_nodes)[:10]:
        peer_orders = _successors_of_type(G, peer_node, "order")
        peer_dates = [
            _str(G.nodes[n], "order_date")
            for n in peer_orders
            if _str(G.nodes[n], "status") == "completed"
        ]
        if peer_dates:
            peer_active.append(1 if _days_ago(max(peer_dates)) < 30 else 0)

    signals["peer_recent_purchase_rate"] = sum(peer_active) / max(len(peer_active), 1) if peer_active else 0.0

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 3,
        "description": f"Traversed products → peer customers ({len(peer_nodes)} peers)",
        "detail": f"peer_recent_purchase_rate={signals['peer_recent_purchase_rate']:.2f}",
    })

    # Hop 1b: Campaign engagement
    campaign_nodes = _successors_of_type(G, customer_node, "campaign")
    campaigns = [G.nodes[n] for n in campaign_nodes]
    signals["campaign_open_rate"] = (
        sum(1 for c in campaigns if _bool(c, "opened")) / len(campaigns)
        if campaigns else 0.0
    )
    signals["campaign_conversion_rate"] = (
        sum(1 for c in campaigns if _bool(c, "converted")) / len(campaigns)
        if campaigns else 0.0
    )

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(campaign_nodes)} campaign touchpoints",
        "detail": (
            f"open_rate={signals['campaign_open_rate']:.2f}, "
            f"conversion_rate={signals['campaign_conversion_rate']:.2f}"
        ),
    })

    # Hop 1c: Sentiment
    interaction_nodes = _successors_of_type(G, customer_node, "interaction")
    interactions = [G.nodes[n] for n in interaction_nodes]
    sentiments = [_str(i, "sentiment") for i in interactions]
    signals["positive_sentiment_rate"] = (
        sentiments.count("positive") / len(sentiments) if sentiments else 0.5
    )

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(interaction_nodes)} interactions",
        "detail": f"positive_sentiment_rate={signals['positive_sentiment_rate']:.2f}",
    })

    return signals, steps


# ─── Fraud risk signal collection ────────────────────────────────────────────

def collect_fraud_signals(
    G: nx.DiGraph,
    order_node: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Collect signals predicting fraud risk for a specific order."""
    signals: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    step_num = 0

    order_attrs = G.nodes[order_node]
    order_date = _str(order_attrs, "order_date")
    order_amount = _float(order_attrs, "total_amount")
    signals["order_amount"] = order_amount

    # Find the customer for this order (predecessor of type customer)
    customer_node = next(
        (n for n in G.predecessors(order_node) if _str(G.nodes[n], "node_type") == "customer"),
        None,
    )

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 0,
        "description": f"Analyzing order {order_node} (${order_amount:.2f})",
        "detail": f"order_date={order_date}, status={_str(order_attrs, 'status')}",
    })

    if not customer_node:
        signals["account_age_days"] = 999
        signals["order_velocity_3d"] = 1
        signals["immediate_return"] = False
        signals["campaign_engagement"] = 0.5
        return signals, steps

    customer_attrs = G.nodes[customer_node]
    signup_date = _str(customer_attrs, "signup_date")
    if order_date and signup_date:
        try:
            od = datetime.date.fromisoformat(order_date)
            sd = datetime.date.fromisoformat(signup_date)
            signals["account_age_days"] = (od - sd).days
        except ValueError:
            signals["account_age_days"] = 999
    else:
        signals["account_age_days"] = 999

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved customer {customer_node} account info",
        "detail": f"signup_date={signup_date}, account_age_at_order={signals['account_age_days']} days",
    })

    # All orders by this customer — check velocity
    all_order_nodes = _successors_of_type(G, customer_node, "order")
    all_orders = [G.nodes[n] for n in all_order_nodes]

    if order_date:
        try:
            od = datetime.date.fromisoformat(order_date)
            orders_in_window = [
                o for o in all_orders
                if _str(o, "order_date")
                and abs((_TODAY - datetime.date.fromisoformat(_str(o, "order_date"))).days - _days_ago(order_date)) <= 3
            ]
        except ValueError:
            orders_in_window = []
    else:
        orders_in_window = []

    signals["order_velocity_3d"] = len(orders_in_window)

    # Check for return on this specific order or within 7 days
    product_nodes = _successors_of_type(G, order_node, "product")
    has_return = any(
        G.edges[order_node, p].get("returned", "False") in ("True", True)
        for p in product_nodes
    )
    signals["immediate_return"] = has_return

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Analyzed order velocity ({len(all_order_nodes)} total orders)",
        "detail": (
            f"orders_in_3day_window={signals['order_velocity_3d']}, "
            f"immediate_return={signals['immediate_return']}"
        ),
    })

    # Campaign engagement
    campaign_nodes = _successors_of_type(G, customer_node, "campaign")
    campaigns = [G.nodes[n] for n in campaign_nodes]
    signals["campaign_engagement"] = (
        sum(1 for c in campaigns if _bool(c, "opened")) / len(campaigns)
        if campaigns else 0.0
    )

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Retrieved {len(campaign_nodes)} campaign touchpoints",
        "detail": f"campaign_engagement={signals['campaign_engagement']:.2f}",
    })

    return signals, steps


# ─── Demand forecast signal collection ───────────────────────────────────────

def collect_demand_signals(
    G: nx.DiGraph,
    category: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Collect signals for demand forecasting for a product category."""
    signals: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []
    step_num = 0

    product_nodes = [
        n for n, attrs in G.nodes(data=True)
        if _str(attrs, "node_type") == "product" and _str(attrs, "category") == category
    ]

    if not product_nodes:
        signals.update({"total_units_sold": 0, "total_revenue": 0.0, "units_30d": 0, "units_60d": 0})
        return signals, steps

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 0,
        "description": f"Found {len(product_nodes)} products in category '{category}'",
        "detail": ", ".join(_str(G.nodes[p], "name") for p in product_nodes[:5]),
    })

    # Count units sold (via incoming edges from orders)
    total_units = 0
    total_revenue = 0.0
    units_30d = 0
    units_60d = 0
    orders_set: set[str] = set()

    for product_node in product_nodes:
        for order_node in G.predecessors(product_node):
            if _str(G.nodes[order_node], "node_type") == "order":
                order_date = _str(G.nodes[order_node], "order_date")
                edge_data = G.edges[order_node, product_node]
                qty = int(edge_data.get("quantity", 1))
                price = float(edge_data.get("unit_price", 0.0))
                orders_set.add(order_node)
                total_units += qty
                total_revenue += qty * price
                days = _days_ago(order_date)
                if days <= 30:
                    units_30d += qty
                if days <= 60:
                    units_60d += qty

    signals["total_units_sold"] = total_units
    signals["total_revenue"] = total_revenue
    signals["units_30d"] = units_30d
    signals["units_60d"] = units_60d
    signals["avg_product_rating"] = (
        sum(_float(G.nodes[p], "avg_rating") for p in product_nodes) / len(product_nodes)
    )

    step_num += 1
    steps.append({
        "step": step_num,
        "hop": 1,
        "description": f"Traversed products → orders ({len(orders_set)} unique orders)",
        "detail": (
            f"total_units={total_units}, total_revenue=${total_revenue:.2f}, "
            f"units_last_30d={units_30d}, units_last_60d={units_60d}"
        ),
    })

    return signals, steps
