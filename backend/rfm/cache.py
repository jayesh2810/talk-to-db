"""
Download Kumo quickstart data from S3, cache parquet locally, and persist LocalGraph.

Flow:
  1. Parquet files live under data/kumo_rfm_cache/parquet/
  2. After first successful LocalGraph build, pickle to data/kumo_rfm_cache/local_graph.pkl
  3. On startup: use pickle if it exists and is newer than all parquet files; else rebuild from parquet.
"""

from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "kumo_rfm_cache"
PARQUET_DIR = DATA_DIR / "parquet"
GRAPH_PICKLE_PATH = DATA_DIR / "local_graph.pkl"
MANIFEST_PATH = DATA_DIR / "manifest.json"

S3_PREFIX = "s3://kumo-sdk-public/rfm-datasets/online-shopping"
PARQUET_FILES = ("users.parquet", "items.parquet", "orders.parquet")


@dataclass
class RFMBundle:
    """Runtime KumoRFM graph + model + dataframes (for filters / indices)."""

    graph: Any
    model: Any
    users: pd.DataFrame
    items: pd.DataFrame
    orders: pd.DataFrame


def _manifest() -> dict[str, Any]:
    return {
        "s3_prefix": S3_PREFIX,
        "files": list(PARQUET_FILES),
        "format_version": 1,
    }


def _ensure_manifest() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST_PATH.exists():
        MANIFEST_PATH.write_text(json.dumps(_manifest(), indent=2))


def _download_parquet_objects() -> None:
    """Fetch parquet from S3 into PARQUET_DIR (skipped if files already exist)."""
    _ensure_manifest()
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    for name in PARQUET_FILES:
        dest = PARQUET_DIR / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        url = f"{S3_PREFIX}/{name}"
        df = pd.read_parquet(url)
        df.to_parquet(dest, index=False)


def _load_parquet_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    users = pd.read_parquet(PARQUET_DIR / "users.parquet")
    items = pd.read_parquet(PARQUET_DIR / "items.parquet")
    orders = pd.read_parquet(PARQUET_DIR / "orders.parquet")
    return users, items, orders


def _parquet_max_mtime() -> float:
    mt = 0.0
    for name in PARQUET_FILES:
        p = PARQUET_DIR / name
        if p.exists():
            mt = max(mt, p.stat().st_mtime)
    return mt


def _graph_cache_valid() -> bool:
    if not GRAPH_PICKLE_PATH.exists():
        return False
    gp = GRAPH_PICKLE_PATH.stat().st_mtime
    pq = _parquet_max_mtime()
    return gp >= pq


def _build_local_graph(users: pd.DataFrame, items: pd.DataFrame, orders: pd.DataFrame) -> Any:
    import kumoai.experimental.rfm as rfm

    return rfm.LocalGraph.from_data(
        {"users": users, "items": items, "orders": orders},
        verbose=False,
    )


def _save_graph(graph: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(GRAPH_PICKLE_PATH, "wb") as f:
        pickle.dump(graph, f, protocol=pickle.HIGHEST_PROTOCOL)


def _load_graph_from_pickle() -> Any:
    with open(GRAPH_PICKLE_PATH, "rb") as f:
        return pickle.load(f)


def load_rfm_bundle(*, force_rebuild_graph: bool = False) -> RFMBundle:
    """
    Ensure dataset on disk, load or build LocalGraph (pickle cache), return bundle with KumoRFM model.
    Requires KUMO_API_KEY in environment before inference (caller runs rfm.init).
    """
    import kumoai.experimental.rfm as rfm

    if force_rebuild_graph:
        clear_graph_cache()

    _download_parquet_objects()
    users, items, orders = _load_parquet_tables()

    if force_rebuild_graph or not _graph_cache_valid():
        graph = _build_local_graph(users, items, orders)
        graph.validate()
        _save_graph(graph)
    else:
        graph = _load_graph_from_pickle()

    model = rfm.KumoRFM(graph, verbose=False)
    return RFMBundle(graph=graph, model=model, users=users, items=items, orders=orders)


def clear_graph_cache() -> None:
    """Remove pickled graph so next load rebuilds from parquet."""
    if GRAPH_PICKLE_PATH.exists():
        GRAPH_PICKLE_PATH.unlink()
