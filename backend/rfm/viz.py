"""Sample nodes/edges for graph visualization from Kumo parquet tables."""

from __future__ import annotations

from typing import Any

from rfm.cache import RFMBundle


def graph_stats(bundle: RFMBundle) -> dict[str, Any]:
    nu = len(bundle.users)
    ni = len(bundle.items)
    no = len(bundle.orders)
    return {
        "node_count": nu + ni,
        "edge_count": no,
        "node_types": {"user": nu, "item": ni},
        "edge_types": {"ordered": no},
    }


def graph_sample(bundle: RFMBundle, *, limit: int = 200) -> dict[str, Any]:
    """
    Subgraph from the first ``limit`` order rows: users and items involved,
    with edges user → item per order.
    """
    stats = graph_stats(bundle)
    orders = bundle.orders.head(max(limit, 1))
    uids = orders["user_id"].unique()
    iids = orders["item_id"].unique()

    user_rows = bundle.users[bundle.users["user_id"].isin(uids)]
    item_rows = bundle.items[bundle.items["item_id"].isin(iids)]

    nodes: list[dict[str, str]] = []
    seen: set[str] = set()

    for _, r in user_rows.iterrows():
        uid = int(r["user_id"])
        nid = f"user:{uid}"
        if nid not in seen:
            seen.add(nid)
            nodes.append({"id": nid, "label": f"user_{uid}", "type": "user"})

    for _, r in item_rows.iterrows():
        iid = int(r["item_id"])
        nid = f"item:{iid}"
        if nid not in seen:
            seen.add(nid)
            name = str(r.get("item_name", iid))[:48]
            nodes.append({"id": nid, "label": name, "type": "item"})

    edges: list[dict[str, str]] = []
    for _, o in orders.iterrows():
        uid = int(o["user_id"])
        iid = int(o["item_id"])
        su, ti = f"user:{uid}", f"item:{iid}"
        if su in seen and ti in seen:
            edges.append({"source": su, "target": ti, "type": "ordered"})

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": stats["node_count"],
        "total_edges": stats["edge_count"],
    }
