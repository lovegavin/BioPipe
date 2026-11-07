"""Co-expression modules from a topological overlap network.

Builds the signed adjacency ``|r|^beta``, the topological overlap matrix (TOM)
and an average-linkage dendrogram of ``1 - TOM``.  Modules are cut at a fixed
height and then merged when their eigengene correlation exceeds the merge
threshold; modules smaller than ``min_module_size`` are assigned to grey (0).
"""

from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from src.core import Form, StepError
from src.task.step.base import Step

from ._coexpression_common import (
    adjacency,
    correlation,
    expression_matrix,
    module_eigengenes,
    select_features,
    tom,
)


def cut_modules(
    X: np.ndarray,
    beta: float,
    cut_height: float,
    merge_threshold: float,
    min_module_size: int,
):
    if not 0.0 < cut_height < 1.0:
        raise StepError("cut_height must be between 0 and 1")
    if not 0.0 <= merge_threshold < 1.0:
        raise StepError("merge_threshold must be in [0, 1)")
    n = X.shape[1]
    R = correlation(X)
    A = adjacency(R, beta)
    T = tom(A)
    diss = 1.0 - T
    np.fill_diagonal(diss, 0.0)
    condensed = squareform(diss, checks=False)
    if not np.all(np.isfinite(condensed)):
        raise StepError("TOM contains non-finite dissimilarities")
    tree = linkage(condensed, method="average")
    raw = fcluster(tree, t=float(cut_height), criterion="distance").astype(int)

    ids = sorted(int(v) for v in np.unique(raw) if v > 0)
    if len(ids) > 1:
        me_ids, ME, _ = module_eigengenes(X, raw, scale=True)
        C = np.corrcoef(ME, rowvar=False)
        C = np.nan_to_num(C, nan=0.0)
        np.fill_diagonal(C, 1.0)
        if len(me_ids) > 1:
            dist = 1.0 - C
            np.fill_diagonal(dist, 0.0)
            group_tree = linkage(squareform(dist, checks=False), method="average")
            groups = fcluster(
                group_tree, t=1.0 - float(merge_threshold), criterion="distance"
            ).astype(int)
            mapping = {mid: int(groups[i]) for i, mid in enumerate(me_ids)}
            raw = np.array([mapping.get(int(v), 0) for v in raw], dtype=int)

    counts = {int(v): int(np.sum(raw == v)) for v in np.unique(raw) if v > 0}
    keep = {mid for mid, size in counts.items() if size >= int(min_module_size)}
    if not keep:
        raise StepError(
            f"no module with at least {min_module_size} features survived the cut"
        )
    labels = np.array([int(v) if int(v) in keep else 0 for v in raw], dtype=int)

    order = sorted(keep, key=lambda mid: (-int(np.sum(labels == mid)), mid))
    remap = {old: index + 1 for index, old in enumerate(order)}
    labels = np.array([remap.get(int(v), 0) for v in labels], dtype=int)
    sizes = {int(mid): int(np.sum(labels == mid)) for mid in remap.values()}
    return labels, sizes, T, R


class CoexpressionModulesStep(Step):
    """Detect co-expression modules from a TOM dendrogram."""

    provider = "operon-core"
    parameters_file = "coexpression_modules.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "coexpression_modules",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Co-expression modules from topological overlap",
        "description": (
            "Builds the signed adjacency and topological overlap matrix, cuts "
            "an average-linkage dendrogram at a fixed height, merges modules "
            "with correlated eigengenes and assigns small modules to grey."
        ),
        "category": "Omics",
        "icon": "Network",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        "sample",
                        "feature",
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        shape = inputs[0].data.shape if inputs else (0, 0)
        features = min(int(params.get("max_features", 0)) or shape[-1], shape[-1])
        # adjacency + TOM + condensed dissimilarities + linkage
        return (max(int(features) ** 2 * 24, 16 << 20), 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sample"))
        feature_dim = str(params.get("feature_dim", "feature"))
        X, samples, features = expression_matrix(inputs[0], sample_dim, feature_dim)
        keep = select_features(X, int(params.get("max_features", 0) or 0))
        X = X[:, keep]
        chosen = [features[i] for i in keep]
        labels, sizes, T, R = cut_modules(
            X,
            beta=float(params.get("beta", 6)),
            cut_height=float(params.get("cut_height", 0.9)),
            merge_threshold=float(params.get("merge_threshold", 0.75)),
            min_module_size=int(params.get("min_module_size", 30)),
        )
        out_name = str(params.get("output", "modules"))
        data = labels.astype(np.float64).reshape(-1, 1)
        out = Form(
            data=data,
            dims=["feature", "module"],
            labels={
                "feature": {gene: index for index, gene in enumerate(chosen)},
                "module": {"module": 0},
            },
            info={
                "n_features": len(chosen),
                "n_modules": len(sizes),
                "n_grey": int(np.sum(labels == 0)),
                "module_sizes": {str(k): v for k, v in sorted(sizes.items())},
                "beta": float(params.get("beta", 6)),
                "tom_mean": float(np.mean(T)),
            },
        )
        out.validate()
        ctx[out_name] = out

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "modules"))]
        sizes = list(form.info["module_sizes"].values())
        return {
            "n_features": int(form.info["n_features"]),
            "n_modules": int(form.info["n_modules"]),
            "n_grey": int(form.info["n_grey"]),
            "largest_module_size": int(max(sizes)) if sizes else 0,
            "median_module_size": float(np.median(sizes)) if sizes else 0.0,
            "beta": float(form.info["beta"]),
        }
