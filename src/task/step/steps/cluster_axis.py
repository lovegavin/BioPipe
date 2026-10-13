# src/task/step/steps/cluster_axis.py
"""Cluster positions along one axis of a form.

Groups positions along ``dim`` into clusters, using the values
across the other axes as features. The output is a new 2D form:

    dims = [dim, "cluster"]
    data: one integer cluster id per position

Cluster ids are renumbered 0..n-1 in order of first appearance in
the original label order.

Methods
-------
    kmeans         KMeans (scikit-learn). Requires ``n_clusters``.
    hierarchical   Ward hierarchical clustering (scipy). Requires
                   ``n_clusters``.
    louvain        Louvain community detection on a KNN graph
                   (networkx + scikit-learn). Requires
                   ``n_neighbors``; ``resolution`` tunes cluster
                   granularity.

Missing values are filled with the feature mean before clustering.

Params:
    dim            : dimension to cluster along (required)
    method         : "kmeans" | "hierarchical" | "louvain" (required)
    n_clusters     : number of clusters (kmeans, hierarchical)
    n_neighbors    : KNN size for louvain (default 15)
    resolution     : Louvain resolution (default 1.0)
    random_state   : random seed for kmeans / louvain (default 0)
    output         : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._axis_contracts import SCHEMAS, CONTRACTS, estimate_axis
from ._microbiome import metadata


_METHODS = ("kmeans", "hierarchical", "louvain")


class ClusterAxisStep(Step):
    """Cluster positions along one axis."""

    name = "cluster_axis"
    inputs_arity = 1
    outputs = []
    title = 'Clustering'
    category = 'Analysis'
    builtin_package = 'biopipe-core'
    legacy_parameters = False
    parameters_schema = SCHEMAS['cluster_axis']
    input_contracts, output_contract = CONTRACTS['cluster_axis']
    output_parameter = 'output'

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate_axis(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        method = ctx.step_params.get("method")
        n_clusters = ctx.step_params.get("n_clusters")
        n_neighbors = int(ctx.step_params.get("n_neighbors", 15))
        resolution = float(ctx.step_params.get("resolution", 1.0))
        random_state = int(ctx.step_params.get("random_state", 0))
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("cluster_axis: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"cluster_axis: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if method not in _METHODS:
            raise StepError(
                f"cluster_axis: method must be one of {list(_METHODS)}, "
                f"got {method!r}"
            )
        if form.data.ndim < 2:
            raise StepError(
                f"cluster_axis: input must have at least 2 dims, "
                f"got ndim={form.data.ndim}"
            )
        if method in ("kmeans", "hierarchical"):
            if n_clusters is None:
                raise StepError(
                    f"cluster_axis/{method}: 'n_clusters' is required"
                )
            n_clusters = int(n_clusters)
            if n_clusters < 2:
                raise StepError(
                    f"cluster_axis: n_clusters must be >= 2, "
                    f"got {n_clusters}"
                )
        if method == "louvain":
            if n_neighbors < 1:
                raise StepError(
                    f"cluster_axis: n_neighbors must be >= 1, "
                    f"got {n_neighbors}"
                )

        axis = form.dims.index(dim)
        moved = np.moveaxis(form.data, axis, 0).astype(np.float64)
        n_positions = moved.shape[0]
        flat = moved.reshape(n_positions, -1)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(flat)
        else:
            missing = flat == missing_code

        with np.errstate(invalid="ignore"):
            col_mean = np.nanmean(np.where(missing, np.nan, flat), axis=0)
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)
        filled = np.where(missing, col_mean, flat)

        if method == "kmeans":
            labels = _kmeans(filled, n_clusters, random_state)
        elif method == "hierarchical":
            labels = _hierarchical(filled, n_clusters)
        else:
            labels = _louvain(
                filled, n_neighbors, resolution, random_state
            )

        labels = _renumber(labels)
        n_found = int(labels.max()) + 1 if labels.size else 0

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        ordered_labels = [
            pos_to_label.get(i, f"#{i}") for i in range(n_positions)
        ]

        data = labels.astype(np.float32).reshape(-1, 1)
        info, axes = metadata(form, [dim], 'clusters')
        ctx[out_name] = Form(
            data=data,
            dims=[dim, "cluster"],
            labels={
                dim: dict(form.labels[dim]),
                "cluster": {"cluster": 0},
            },
            info=info, axis_info=axes,
        )

        sizes: dict[str, int] = {}
        for c in labels:
            sizes[str(int(c))] = sizes.get(str(int(c)), 0) + 1

        self._export_data = {
            "dim": dim,
            "method": method,
            "n_clusters": n_found,
            "n_positions": int(n_positions),
            "n_features": int(filled.shape[1]),
            "cluster_sizes": sizes,
            "labels": ordered_labels,
            "clusters": [int(c) for c in labels],
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "method": method,
            "n_clusters": n_found,
            "n_positions": int(n_positions),
        }

        print(
            f"[cluster_axis] method='{method}' dim='{dim}' "
            f"n_positions={n_positions} -> {n_found} clusters"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _kmeans(X: np.ndarray, k: int, random_state: int) -> np.ndarray:
    try:
        from sklearn.cluster import KMeans
    except ImportError as exc:
        raise StepError(
            "cluster_axis/kmeans: scikit-learn is required."
        ) from exc
    km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
    return km.fit_predict(X)


def _hierarchical(X: np.ndarray, k: int) -> np.ndarray:
    try:
        from scipy.cluster.hierarchy import fcluster, linkage
    except ImportError as exc:
        raise StepError(
            "cluster_axis/hierarchical: scipy is required."
        ) from exc
    if X.shape[0] < 2:
        raise StepError(
            "cluster_axis/hierarchical: need at least 2 positions"
        )
    Z = linkage(X, method="ward")
    return fcluster(Z, t=k, criterion="maxclust")


def _louvain(X: np.ndarray, n_neighbors: int, resolution: float,
             random_state: int) -> np.ndarray:
    try:
        from sklearn.neighbors import NearestNeighbors
        import networkx as nx
    except ImportError as exc:
        raise StepError(
            "cluster_axis/louvain: scikit-learn and networkx are "
            "required."
        ) from exc

    n = X.shape[0]
    if n < 2:
        raise StepError(
            "cluster_axis/louvain: need at least 2 positions"
        )
    k = min(n_neighbors, n - 1)

    nn = NearestNeighbors(n_neighbors=k + 1).fit(X)
    distances, indices = nn.kneighbors(X)

    G = nx.Graph()
    for i in range(n):
        for j_pos in range(1, k + 1):
            j = int(indices[i, j_pos])
            d = float(distances[i, j_pos])
            weight = 1.0 / (d + 1e-9)
            if G.has_edge(i, j):
                G[i][j]["weight"] = max(G[i][j]["weight"], weight)
            else:
                G.add_edge(i, j, weight=weight)

    communities = nx.algorithms.community.louvain_communities(
        G, weight="weight", resolution=resolution, seed=random_state,
    )
    labels = np.zeros(n, dtype=int)
    for cid, members in enumerate(communities):
        for m in members:
            labels[int(m)] = cid
    return labels


def _renumber(labels: np.ndarray) -> np.ndarray:
    """Renumber cluster ids to 0..n-1 in order of first appearance."""
    seen: dict[int, int] = {}
    out = np.empty_like(labels)
    for i, v in enumerate(labels):
        vi = int(v)
        if vi not in seen:
            seen[vi] = len(seen)
        out[i] = seen[vi]
    return out