"""
Build a NetworkX DiGraph from SQLite tables and persist it as GraphML.

Graph structure:
  Nodes: customer:{id}, product:{id}, order:{id}, interaction:{id}, campaign:{id}
  Edges: placed, contains, bought_by, had_interaction, received_campaign

GraphML constraints:
  - Attribute values must be str, int, float, or bool.
  - None → empty string ""
  - Booleans stored as "True"/"False" strings (GraphML booleans are unreliable).
  - Dates are already ISO strings from SQLite.
"""

import sys
import sqlite3
from pathlib import Path

import networkx as nx

GRAPH_PATH = Path(__file__).parent.parent / "data" / "graph.graphml"


def _clean(value: object) -> str | int | float:
    """Convert a SQLite value to a GraphML-safe scalar."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return value
    return str(value)


def _node_attrs(row: sqlite3.Row) -> dict:
    """Convert a SQLite Row to a dict of GraphML-safe attributes."""
    return {k: _clean(row[k]) for k in row.keys()}


def build_graph(conn: sqlite3.Connection) -> nx.DiGraph:
    """Build the entity-relationship graph from all SQLite tables."""
    G = nx.DiGraph()

    for row in conn.execute("SELECT * FROM customers"):
        G.add_node(f"customer:{row['customer_id']}", node_type="customer", **_node_attrs(row))

    for row in conn.execute("SELECT * FROM products"):
        G.add_node(f"product:{row['product_id']}", node_type="product", **_node_attrs(row))

    for row in conn.execute("SELECT * FROM orders"):
        G.add_node(f"order:{row['order_id']}", node_type="order", **_node_attrs(row))
        G.add_edge(
            f"customer:{row['customer_id']}",
            f"order:{row['order_id']}",
            edge_type="placed",
            date=str(row["order_date"] or ""),
        )

    for row in conn.execute(
        "SELECT oi.*, o.customer_id FROM order_items oi JOIN orders o ON oi.order_id = o.order_id"
    ):
        G.add_node(
            f"item:{row['item_id']}",
            node_type="item",
            **_node_attrs(row),
        )
        G.add_edge(
            f"order:{row['order_id']}",
            f"product:{row['product_id']}",
            edge_type="contains",
            quantity=int(row["quantity"] or 0),
            unit_price=float(row["unit_price"] or 0.0),
            returned=_clean(bool(row["returned"])),
        )
        # Reverse edge enables the multi-hop peer signal
        G.add_edge(
            f"product:{row['product_id']}",
            f"customer:{row['customer_id']}",
            edge_type="bought_by",
        )

    for row in conn.execute("SELECT * FROM interactions"):
        G.add_node(f"interaction:{row['interaction_id']}", node_type="interaction", **_node_attrs(row))
        G.add_edge(
            f"customer:{row['customer_id']}",
            f"interaction:{row['interaction_id']}",
            edge_type="had_interaction",
        )

    for row in conn.execute("SELECT * FROM campaign_touchpoints"):
        G.add_node(f"campaign:{row['touchpoint_id']}", node_type="campaign", **_node_attrs(row))
        G.add_edge(
            f"customer:{row['customer_id']}",
            f"campaign:{row['touchpoint_id']}",
            edge_type="received_campaign",
        )

    _add_computed_attrs(G)
    return G


def _add_computed_attrs(G: nx.DiGraph) -> None:
    """
    Enrich customer and product nodes with pre-computed relationship stats.

    This allows factual MATCH queries to filter on derived fields like
    order_count, total_spent, return_rate directly via WHERE clauses,
    without requiring runtime traversal.
    """
    for node_id, attrs in G.nodes(data=True):
        if attrs.get("node_type") != "customer":
            continue

        order_nodes = [n for n in G.successors(node_id)
                       if G.nodes[n].get("node_type") == "order"]
        orders = [G.nodes[n] for n in order_nodes]

        completed = [o for o in orders if o.get("status") == "completed"]
        returned  = [o for o in orders if o.get("status") == "returned"]

        attrs["order_count"]           = len(orders)
        attrs["completed_order_count"] = len(completed)
        attrs["return_count"]          = len(returned)
        attrs["total_spent"]           = round(
            sum(float(o.get("total_amount") or 0) for o in completed), 2
        )
        attrs["avg_order_value"]       = round(
            attrs["total_spent"] / len(completed), 2
        ) if completed else 0.0

        interaction_nodes = [n for n in G.successors(node_id)
                             if G.nodes[n].get("node_type") == "interaction"]
        interactions = [G.nodes[n] for n in interaction_nodes]
        sentiments = [i.get("sentiment", "") for i in interactions]
        attrs["interaction_count"]          = len(interactions)
        attrs["negative_interaction_count"] = sentiments.count("negative")

    for node_id, attrs in G.nodes(data=True):
        if attrs.get("node_type") != "product":
            continue

        order_nodes = [n for n in G.predecessors(node_id)
                       if G.nodes[n].get("node_type") == "order"]
        total_qty = sum(
            int(G.edges[o, node_id].get("quantity") or 1)
            for o in order_nodes
            if G.has_edge(o, node_id)
        )
        attrs["times_ordered"] = len(order_nodes)
        attrs["total_units_sold"] = total_qty


def cast_graph_attributes(G: nx.DiGraph) -> None:
    """
    Normalize attribute types after loading from GraphML.

    GraphML serializes everything as strings. This function converts
    numeric strings back to float/int where expected, and boolean
    strings ("True"/"False") back to the string form traversal.py expects.
    """
    float_attrs = {
        "lifetime_value", "price", "cost", "avg_rating",
        "total_amount", "discount", "unit_price", "resolution_hours",
        "total_spent", "avg_order_value",
    }
    int_attrs = {
        "review_count", "stock_level", "quantity", "delivery_days", "promised_days",
        "order_count", "completed_order_count", "return_count",
        "interaction_count", "negative_interaction_count",
        "times_ordered", "total_units_sold",
    }

    for _, attrs in G.nodes(data=True):
        for attr in float_attrs:
            if attr in attrs and attrs[attr] != "":
                try:
                    attrs[attr] = float(attrs[attr])
                except (ValueError, TypeError):
                    attrs[attr] = 0.0
        for attr in int_attrs:
            if attr in attrs and attrs[attr] != "":
                try:
                    attrs[attr] = int(float(attrs[attr]))
                except (ValueError, TypeError):
                    attrs[attr] = 0

    for _, _, attrs in G.edges(data=True):
        if "quantity" in attrs:
            try:
                attrs["quantity"] = int(float(attrs["quantity"]))
            except (ValueError, TypeError):
                attrs["quantity"] = 0
        if "unit_price" in attrs:
            try:
                attrs["unit_price"] = float(attrs["unit_price"])
            except (ValueError, TypeError):
                attrs["unit_price"] = 0.0


def load_or_build_graph(conn: sqlite3.Connection) -> nx.DiGraph:
    """
    Load the graph from GraphML if cached; build and save it otherwise.

    Pass --rebuild-graph as a CLI argument to force a rebuild even
    when the cache file exists.
    """
    if GRAPH_PATH.exists() and "--rebuild-graph" not in sys.argv:
        print(f"Loading graph from {GRAPH_PATH}...")
        G = nx.read_graphml(str(GRAPH_PATH))
        cast_graph_attributes(G)
        print(f"Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        return G

    print("Building graph from SQLite tables...")
    G = build_graph(conn)

    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(G, str(GRAPH_PATH))
    print(f"Graph saved to {GRAPH_PATH}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G
