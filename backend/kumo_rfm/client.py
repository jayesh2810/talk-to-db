"""
KumoRFM client — loads e-commerce data (local cache first, else S3), builds a
relational graph, and exposes a predict() wrapper around KumoRFM.

On unsupported platforms (e.g. macOS x86_64) a pure-Python shim replaces
the native kumolib extension so the full SDK still works.

Dataset caching:
  Parquet files live under backend/.data_cache/online-shopping/ (see KUMO_DATA_CACHE_DIR,
  KUMO_FORCE_S3).

Model / graph materialization cache:
  After the first successful run, the initialized KumoRFM object (including the
  materialized local graph store) is pickled to disk so later startups skip the
  expensive “materializing graph” step. Invalidate with changed Parquet files,
  KUMO_FORCE_GRAPH_REBUILD=1, kumoai version mismatch, or delete the pickle.

Note: This uses Python pickle for the SDK object; bump CACHE_FORMAT_VERSION if
the on-disk layout must change.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import pickle
import re
from pathlib import Path
from typing import Any

import pandas as pd

# Inject pure-Python NeighborSampler BEFORE any rfm import
from kumo_rfm._kumolib_shim import patch as _patch_kumolib
_patch_kumolib()

import kumoai.experimental.rfm as rfm  # noqa: E402

DATASET_URL = "s3://kumo-sdk-public/rfm-datasets/online-shopping"

# Parquet filenames on S3 and on disk (same names).
_TABLE_SPECS: tuple[tuple[str, str], ...] = (
    ("users", "users.parquet"),
    ("items", "items.parquet"),
    ("orders", "orders.parquet"),
)

CACHE_FORMAT_VERSION = 1
MODEL_PICKLE_NAME = "kumo_rfm_model.pkl"
MANIFEST_NAME = "model_cache_manifest.json"

_graph: rfm.Graph | None = None
_model: rfm.KumoRFM | None = None
_dataframes: dict[str, pd.DataFrame] = {}


def _ensure_api_key() -> None:
    api_key = os.environ.get("KUMO_API_KEY")
    if not api_key:
        raise RuntimeError(
            "KUMO_API_KEY is not set. "
            "Get a free key at https://kumorfm.ai and add it to backend/.env"
        )


def _cache_dir() -> Path:
    override = os.environ.get("KUMO_DATA_CACHE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / ".data_cache" / "online-shopping"


def _cache_paths(cache_root: Path) -> dict[str, Path]:
    return {name: cache_root / filename for name, filename in _TABLE_SPECS}


def _cache_complete(paths: dict[str, Path]) -> bool:
    return all(p.is_file() and p.stat().st_size > 0 for p in paths.values())


def _kumoai_version() -> str:
    try:
        return importlib.metadata.version("kumoai")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _dataset_fingerprint(paths: dict[str, Path]) -> str:
    """Stable fingerprint from Parquet paths (size + mtime); cheap vs hashing files."""
    parts: list[str] = []
    for name, _fn in _TABLE_SPECS:
        p = paths[name]
        if not p.is_file():
            return ""
        st = p.stat()
        parts.append(f"{name}:{st.st_size}:{st.st_mtime_ns}")
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def _manifest_path(root: Path) -> Path:
    return root / MANIFEST_NAME


def _model_pickle_path(root: Path) -> Path:
    return root / MODEL_PICKLE_NAME


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _try_load_model_pickle(root: Path, expected_fp: str) -> rfm.KumoRFM | None:
    mp = _model_pickle_path(root)
    mf = _manifest_path(root)
    if not mp.is_file() or not mf.is_file():
        return None
    try:
        manifest = json.loads(mf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if manifest.get("cache_format_version") != CACHE_FORMAT_VERSION:
        return None
    if manifest.get("dataset_fingerprint") != expected_fp:
        return None
    if manifest.get("kumoai_version") != _kumoai_version():
        return None
    try:
        with mp.open("rb") as f:
            model = pickle.load(f)
    except Exception as e:
        print(f"[kumo] Could not load model cache ({e!r}); rebuilding...")
        return None
    if not isinstance(model, rfm.KumoRFM):
        return None
    # Lazy HTTP client must be recreated against current SDK session.
    if hasattr(model, "_client"):
        model._client = None
    return model


def _save_model_pickle(root: Path, model: rfm.KumoRFM, fingerprint: str) -> None:
    try:
        root.mkdir(parents=True, exist_ok=True)
        mp = _model_pickle_path(root)
        tmp = mp.with_suffix(mp.suffix + ".tmp")
        with tmp.open("wb") as f:
            pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
        tmp.replace(mp)
        _write_json_atomic(
            _manifest_path(root),
            {
                "cache_format_version": CACHE_FORMAT_VERSION,
                "dataset_fingerprint": fingerprint,
                "kumoai_version": _kumoai_version(),
            },
        )
        print(f"[kumo] Saved materialized model to {mp}")
    except Exception as e:
        print(f"[kumo] Warning: could not save model cache ({e!r}).")


def load_data() -> dict[str, pd.DataFrame]:
    """
    Load e-commerce tables: from local disk cache if complete, else from S3
    (then write cache). In-memory singleton for the current process.
    """
    global _dataframes

    if _dataframes:
        return _dataframes

    root = _cache_dir()
    paths = _cache_paths(root)
    force_s3 = os.environ.get("KUMO_FORCE_S3", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    use_disk = _cache_complete(paths) and not force_s3

    if use_disk:
        print(f"[kumo] Loading e-commerce dataset from local cache ({root})...")
        _dataframes = {name: pd.read_parquet(paths[name]) for name, _ in _TABLE_SPECS}
    else:
        if force_s3 and _cache_complete(paths):
            print("[kumo] KUMO_FORCE_S3 set — re-downloading dataset from S3...")
        else:
            print("[kumo] Downloading e-commerce dataset from S3 (caching to disk)...")
        root.mkdir(parents=True, exist_ok=True)
        _dataframes = {}
        for name, filename in _TABLE_SPECS:
            s3_uri = f"{DATASET_URL}/{filename}"
            df = pd.read_parquet(s3_uri)
            dest = paths[name]
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            df.to_parquet(tmp, index=False)
            tmp.replace(dest)
            _dataframes[name] = df

    for name, df in _dataframes.items():
        print(f"  {name}: {len(df)} rows, {list(df.columns)}")

    return _dataframes


def init_model() -> rfm.KumoRFM:
    """Initialize the KumoRFM graph and model (idempotent)."""
    global _graph, _model

    if _model is not None:
        return _model

    _ensure_api_key()
    rfm.init()

    dfs = load_data()
    cache_root = _cache_dir()
    parquet_paths = _cache_paths(cache_root)
    fingerprint = _dataset_fingerprint(parquet_paths)

    force_rebuild = os.environ.get(
        "KUMO_FORCE_GRAPH_REBUILD",
        "",
    ).strip().lower() in ("1", "true", "yes")

    if fingerprint and not force_rebuild:
        cached = _try_load_model_pickle(cache_root, fingerprint)
        if cached is not None:
            _model = cached
            print("[kumo] Restored materialized KumoRFM from local disk cache.")
            # Lightweight graph for introspection / API symmetry (no second materialization).
            _graph = rfm.Graph.from_data(dfs, verbose=False)
            print("[kumo] Ready.")
            return _model

    if force_rebuild:
        print("[kumo] KUMO_FORCE_GRAPH_REBUILD set — rebuilding graph and model...")

    print("[kumo] Building relational graph (auto-inferring links)...")
    _graph = rfm.Graph.from_data(dfs)

    print("[kumo] Initializing KumoRFM model (materializing graph)...")
    _model = rfm.KumoRFM(_graph)

    if fingerprint:
        _save_model_pickle(cache_root, _model, fingerprint)

    print("[kumo] Ready.")
    return _model


def get_model() -> rfm.KumoRFM:
    if _model is None:
        raise RuntimeError("KumoRFM model not initialized. Call init_model() first.")
    return _model


def get_graph() -> rfm.Graph:
    if _graph is None:
        raise RuntimeError("KumoRFM graph not initialized. Call init_model() first.")
    return _graph


def get_dataframes() -> dict[str, pd.DataFrame]:
    if not _dataframes:
        load_data()
    return _dataframes


def _pql_has_temporal_window(pql: str) -> bool:
    """True if PQL uses a time-range clause like `, 30, days` (needs anchor time)."""
    return bool(re.search(r",\s*\d+\s*,\s*days", pql, re.IGNORECASE))


def _default_predict_anchor_time() -> pd.Timestamp | None:
    """
    KumoRFM derives anchor time from max(timestamp) by default. For forward-looking
    windows (next N days), that leaves no future/past overlap with edges and the
    local sampler can omit tables (KeyError). Shift anchor earlier so windows hit data.
    """
    dfs = get_dataframes()
    orders = dfs.get("orders")
    if orders is None or len(orders) == 0:
        return None
    date_col = "date" if "date" in orders.columns else None
    if date_col is None:
        return None
    tmax = pd.to_datetime(orders[date_col]).max()
    offset_days = int(os.environ.get("KUMO_ANCHOR_OFFSET_DAYS", "60"))
    return tmax - pd.Timedelta(days=offset_days)


def predict(pql_query: str, indices: list | None = None) -> pd.DataFrame:
    """
    Run a PQL prediction query against KumoRFM.

    Args:
        pql_query: A valid KumoRFM PQL query string.
        indices: Optional list of entity IDs to predict for.

    Returns:
        A pandas DataFrame with prediction results.
    """
    model = get_model()

    kwargs: dict[str, Any] = {}
    if indices:
        kwargs["indices"] = indices

    if _pql_has_temporal_window(pql_query):
        anchor = _default_predict_anchor_time()
        if anchor is not None:
            kwargs["anchor_time"] = anchor

    result = model.predict(pql_query, **kwargs)
    return result


def get_schema_info() -> dict[str, Any]:
    """Return schema metadata about the loaded tables for the LLM prompt."""
    dfs = get_dataframes()

    tables = {}
    for name, df in dfs.items():
        tables[name] = {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "row_count": len(df),
            "sample_values": {
                col: df[col].dropna().head(3).tolist()
                for col in df.columns
            },
        }

    return tables
