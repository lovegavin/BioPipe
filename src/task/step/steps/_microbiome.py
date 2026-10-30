"""Shared declarations and resource estimates for abundance-table operators.

Kernels remain full-memory operations. Estimates account for float64 temporary
arrays and quadratic outputs, and use the existing admission/spill machinery.
"""
import math

import numpy as np

from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata


def metadata(form, keep, representation, selections=None):
    info, axes = project_metadata(form, selections, keep_dims=keep, derived=True)
    info.update(missing_code=np.nan, representation=representation)
    return info, axes


def estimate(name, inputs, params, profiles):
    if not inputs:
        return 0, 0
    form = inputs[0]
    size = math.prod(form.data.shape)
    dim = params.get("dim", params.get("dist_dim", "sample"))
    axis = form.dims.index(dim) if dim in form.dims else 0
    n = form.data.shape[axis]
    label_bytes = sum(sum(len(v) for v in f.labels.values()) * 192 for f in inputs)
    workspace, output = size * 96 + label_bytes, size * 4 + label_bytes
    if name in {"distance_matrix", "correlation"}:
        workspace = size * 40 + n * n * 48 + label_bytes
        output = n * n * 4 + n * 384
    elif name == "reduce":
        method = params.get("method", "pca")
        observations = n if method == "pcoa" else form.data.shape[1 - axis]
        k = min(int(params.get("n_components", 2 if method in {"umap", "tsne"} else 10)), min(form.data.shape))
        workspace = size * 128 + observations * observations * (128 if method in {"tsne", "umap"} else 16) + label_bytes
        output = observations * k * 4 + (observations + k) * 192 + label_bytes
    elif name == "diversity":
        metrics = params.get("metrics", [])
        count = 1 if isinstance(metrics, str) else len(metrics)
        output = size // max(1, n) * count * 4 + label_bytes
    elif name == "join":
        rows = form.data.shape[0]
        columns = form.data.shape[1] + inputs[1].data.shape[1]
        output = rows * columns * 4 + label_bytes
        workspace = output * 6
    elif name == "permanova":
        # Permutations run sequentially. Worst case: each row has a group.
        groups = len(params["groups"]) if params.get("groups") else n
        comparisons = 1 + groups * (groups - 1) // 2 if params.get("pairwise") else 1
        workspace = n * n * 96 + comparisons * 2048 + label_bytes
        output = comparisons * (4 * 4 + 192)
    elif name == "barplot":
        workspace, output = max(workspace, 16 * 1024**2), 0
    override = profiles.get(name, {})
    return int(override.get("workspace_mb", workspace / 1024**2) * 1024**2), int(override.get("output_mb", output / 1024**2) * 1024**2)
