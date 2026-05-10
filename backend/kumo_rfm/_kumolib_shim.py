"""
Pure-Python fallback for kumoai.kumolib.NeighborSampler.

The official kumoai SDK ships a compiled C++ extension (kumolib) that only
supports Linux x86_64, macOS arm64, and Windows x86_64.  This module
provides a NumPy-only reimplementation of the NeighborSampler so the SDK
can run on *any* platform (macOS x86_64 in particular).

The shim must be injected into sys.modules BEFORE any import of
kumoai.experimental.rfm — see `patch()` below.
"""

from __future__ import annotations

import sys
import types
from collections import defaultdict

import numpy as np


class NeighborSampler:
    """Temporal heterogeneous neighbor sampler on a CSC graph."""

    def __init__(
        self,
        table_names: list[str],
        edge_types: list[tuple[str, str, str]],
        colptr_dict: dict[str, np.ndarray],
        row_dict: dict[str, np.ndarray],
        time_dict: dict[str, np.ndarray],
    ) -> None:
        self._table_names = table_names
        self._edge_types = edge_types
        self._colptr = colptr_dict
        self._row = row_dict
        self._time = time_dict

        self._edge_src: dict[str, str] = {}
        self._edge_dst: dict[str, str] = {}
        for src, fkey, dst in edge_types:
            key = f"{src}__{fkey}__{dst}"
            self._edge_src[key] = src
            self._edge_dst[key] = dst
            rev = f"rev_{src}__{fkey}__{dst}"
            self._edge_src[rev] = dst
            self._edge_dst[rev] = src

    def sample(
        self,
        num_neighbors_dict: dict[str, list[int]],
        unix_time_offset_dict: dict[str, list[list[int | None]]],
        entity_table_name: str,
        seed_index: np.ndarray,
        seed_time: np.ndarray,
    ) -> tuple[
        dict[str, np.ndarray],
        dict[str, np.ndarray],
        dict[str, np.ndarray],
        dict[str, np.ndarray],
        dict[str, np.ndarray],
        dict[str, np.ndarray],
    ]:
        num_hops = 0
        for v in num_neighbors_dict.values():
            num_hops = max(num_hops, len(v))
        for v in unix_time_offset_dict.values():
            num_hops = max(num_hops, len(v))

        node_dict: dict[str, list[int]] = defaultdict(list)
        time_for_node: dict[str, list[int]] = defaultdict(list)
        batch_dict: dict[str, list[int]] = defaultdict(list)

        seed_index = np.asarray(seed_index, dtype=np.int64)
        seed_time = np.asarray(seed_time, dtype=np.int64)
        num_seeds = len(seed_index)

        node_dict[entity_table_name] = seed_index.tolist()
        time_for_node[entity_table_name] = seed_time.tolist()
        batch_dict[entity_table_name] = list(range(num_seeds))

        num_sampled_nodes_dict: dict[str, list[list[int]]] = defaultdict(
            lambda: [[] for _ in range(num_hops + 1)]
        )
        num_sampled_nodes_dict[entity_table_name][0] = [1] * num_seeds

        all_edge_keys = set(self._colptr.keys())
        sampled_rows: dict[str, list[int]] = defaultdict(list)
        sampled_cols: dict[str, list[int]] = defaultdict(list)
        num_sampled_edges_raw: dict[str, list[list[int]]] = defaultdict(
            lambda: [[] for _ in range(num_hops)]
        )

        frontier: dict[str, list[tuple[int, int, int]]] = {
            entity_table_name: [
                (int(seed_index[i]), int(seed_time[i]), i)
                for i in range(num_seeds)
            ]
        }

        for hop in range(num_hops):
            next_frontier: dict[str, list[tuple[int, int, int]]] = defaultdict(
                list
            )

            for edge_key in all_edge_keys:
                src_table = self._edge_src.get(edge_key)
                dst_table = self._edge_dst.get(edge_key)
                if src_table is None or dst_table is None:
                    continue

                nn_list = num_neighbors_dict.get(edge_key, [])
                toff_list = unix_time_offset_dict.get(edge_key, [])

                if hop < len(toff_list):
                    offsets = toff_list[hop]
                    nn = -1
                else:
                    nn = nn_list[hop] if hop < len(nn_list) else 0
                    offsets = None

                if nn == 0 and offsets is None:
                    continue

                colptr = self._colptr[edge_key]
                row = self._row[edge_key]
                src_time_arr = self._time.get(
                    self._edge_src.get(edge_key, ""), None
                )

                current_nodes = frontier.get(dst_table, [])
                if not current_nodes:
                    for _ in range(num_seeds):
                        num_sampled_edges_raw[edge_key][hop].append(0)
                        num_sampled_nodes_dict[src_table][hop + 1].append(0)
                    continue

                for node_id, anchor_t, batch_id in current_nodes:
                    if node_id < 0 or node_id >= len(colptr) - 1:
                        num_sampled_edges_raw[edge_key][hop].append(0)
                        num_sampled_nodes_dict[src_table][hop + 1].append(0)
                        continue

                    start = int(colptr[node_id])
                    end = int(colptr[node_id + 1])
                    neighbors = row[start:end]

                    if len(neighbors) == 0:
                        num_sampled_edges_raw[edge_key][hop].append(0)
                        num_sampled_nodes_dict[src_table][hop + 1].append(0)
                        continue

                    if offsets is not None:
                        start_off, end_off = offsets
                        if src_time_arr is not None:
                            n_times = src_time_arr[neighbors]
                            mask = n_times <= anchor_t - (end_off or 0)
                            if start_off is not None:
                                mask &= n_times >= anchor_t - start_off
                            neighbors = neighbors[mask]
                        sampled = neighbors
                    elif src_time_arr is not None:
                        n_times = src_time_arr[neighbors]
                        valid = neighbors[n_times <= anchor_t]
                        if nn > 0 and len(valid) > nn:
                            idx = np.random.choice(
                                len(valid), size=nn, replace=False
                            )
                            sampled = valid[idx]
                        else:
                            sampled = valid
                    else:
                        if nn > 0 and len(neighbors) > nn:
                            idx = np.random.choice(
                                len(neighbors), size=nn, replace=False
                            )
                            sampled = neighbors[idx]
                        else:
                            sampled = neighbors

                    count = len(sampled)
                    num_sampled_edges_raw[edge_key][hop].append(count)
                    num_sampled_nodes_dict[src_table][hop + 1].append(count)

                    for s in sampled:
                        s_int = int(s)
                        node_dict[src_table].append(s_int)
                        t = (
                            int(src_time_arr[s_int])
                            if src_time_arr is not None
                            else anchor_t
                        )
                        time_for_node[src_table].append(t)
                        batch_dict[src_table].append(batch_id)
                        sampled_rows[edge_key].append(s_int)
                        sampled_cols[edge_key].append(node_id)
                        next_frontier[src_table].append(
                            (s_int, t, batch_id)
                        )

            frontier = dict(next_frontier)

        out_node: dict[str, np.ndarray] = {}
        out_batch: dict[str, np.ndarray] = {}
        # Ensure every known table appears in the output even if no nodes
        # were sampled for it — the SDK's local sampler indexes node_dict
        # by every table in columns_dict and will KeyError on missing keys.
        all_tables = set(self._table_names) | set(node_dict.keys())
        for tbl in all_tables:
            out_node[tbl] = np.array(node_dict.get(tbl, []), dtype=np.int64)
            out_batch[tbl] = np.array(batch_dict.get(tbl, []), dtype=np.int64)

        out_row: dict[str, np.ndarray] = {}
        out_col: dict[str, np.ndarray] = {}
        out_nsn: dict[str, np.ndarray] = {}
        out_nse: dict[str, np.ndarray] = {}

        for edge_key in all_edge_keys:
            if edge_key in sampled_rows and len(sampled_rows[edge_key]) > 0:
                out_row[edge_key] = np.array(
                    sampled_rows[edge_key], dtype=np.int64
                )
                out_col[edge_key] = np.array(
                    sampled_cols[edge_key], dtype=np.int64
                )
            else:
                out_row[edge_key] = np.array([], dtype=np.int64)
                out_col[edge_key] = np.array([], dtype=np.int64)

            hops = num_sampled_edges_raw.get(edge_key, [[] for _ in range(num_hops)])
            flat = [sum(h) for h in hops]
            out_nse[edge_key] = np.array(flat, dtype=np.int64)

        for tbl in set(self._table_names) | set(node_dict.keys()):
            hops = num_sampled_nodes_dict.get(tbl, [[] for _ in range(num_hops + 1)])
            flat = [sum(h) for h in hops]
            out_nsn[tbl] = np.array(flat, dtype=np.int64)

        return out_row, out_col, out_node, out_batch, out_nsn, out_nse


def patch() -> None:
    """Inject a fake ``kumoai.kumolib`` module into sys.modules so that
    ``kumoai.experimental.rfm.backend.local`` can import without error."""
    if "kumoai.kumolib" in sys.modules:
        return

    mod = types.ModuleType("kumoai.kumolib")
    mod.__package__ = "kumoai"
    mod.NeighborSampler = NeighborSampler  # type: ignore[attr-defined]
    sys.modules["kumoai.kumolib"] = mod
