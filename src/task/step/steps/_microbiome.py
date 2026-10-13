"""Shared declarations and resource estimates for abundance-table operators.

Kernels remain full-memory operations. Estimates account for float64 temporary
arrays and quadratic outputs, and use the existing admission/spill machinery.
"""
import math

import numpy as np

from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata


def field(kind, **kwargs):
    return {"type": kind, **kwargs}


def enum(values, default=None):
    return {"type": "string", "enum": list(values), **({"default": default} if default is not None else {})}


def strings(**kwargs):
    return field("array", **{"items": field("string"), **kwargs})


def schema(properties, required):
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


DIM = field("string", minLength=1)
SCHEMAS = {
    "diversity": schema({"dim": DIM, "metrics": {"oneOf": [enum(["shannon", "simpson", "richness", "evenness", "gini"]),
        strings(minItems=1, uniqueItems=True, items=enum(["shannon", "simpson", "richness", "evenness", "gini"]))]}}, ["dim", "metrics"]),
    "distance_matrix": schema({"dim": DIM, "metric": enum(["euclidean", "manhattan", "cosine", "correlation", "braycurtis", "jaccard", "hamming"], "euclidean"),
        "max_positions": field(["integer", "null"], minimum=1, default=None, description="Optional position limit; null uses the memory budget without a fixed count cap.")}, ["dim"]),
    "correlation": schema({"dim": DIM, "metric": enum(["pearson", "spearman", "kendall", "cosine", "jaccard", "overlap"], "pearson"),
        "min_valid": field("integer", minimum=2, default=3), "max_positions": field(["integer", "null"], minimum=1, default=None)}, ["dim"]),
    "reduce": schema({"dim": DIM, "method": enum(["pca", "pcoa", "umap", "tsne"], "pca"),
        "n_components": field("integer", minimum=1, description="Omit for method default: PCA/PCoA 10, UMAP/t-SNE 2."),
        "standardize": field("boolean", default=True), "random_state": field("integer", default=0),
        "n_neighbors": field("integer", minimum=2), "min_dist": field("number", minimum=0), "metric": field("string"),
        "perplexity": field("number", exclusiveMinimum=0), "learning_rate": {"anyOf": [field("number", exclusiveMinimum=0), {"const": "auto"}]},
        "n_iter": field("integer", minimum=250)}, ["dim"]),
    "join": schema({"dim": DIM, "columns": {"oneOf": [{"const": "all"}, strings(minItems=1, uniqueItems=True)], "default": "all"},
        "how": enum(["inner", "left"], "inner"), "prefix": field("string", default="")}, ["dim"]),
    "aggregate": schema({"dim": DIM, "group_col": DIM, "method": enum(["sum", "mean", "median", "min", "max", "count"], "sum")}, ["dim", "group_col"]),
    "permanova": schema({"dist_dim": field("string", default="sample"), "group_dim": DIM, "group_label": DIM,
        "groups": strings(minItems=2, uniqueItems=True), "pairwise": field("boolean", default=False),
        "n_permutations": field("integer", minimum=1, default=999), "random_state": field("integer", default=0)}, ["group_label"]),
    "barplot": schema({"dim": DIM, "sample_dim": DIM, "filename": DIM, "top_n": field(["integer", "null"], minimum=0, default=20),
        "other_label": field("string", default="Other"), "normalize": field("boolean", default=True), "title": field("string"),
        "xlabel": field("string"), "ylabel": field("string"), "cmap": field("string", default="tab20"),
        "figsize": field("array", items=field("number", exclusiveMinimum=0), minItems=2, maxItems=2),
        "legend": field("boolean", default=True), "legend_ncol": field("integer", minimum=1, default=3),
        "rotate_labels": field("boolean", default=True)}, ["dim", "sample_dim", "filename"]),
}


def projected(representation, **kwargs):
    return {"mode": "project", "derived": True, "info": {"missing_code": MISSING,
            "representation": {"type": "string", "const": representation}}, **kwargs}


PAIR_AXIS = {"name": {"param": "dim", "suffix": "_b"}, "labels_from": param("dim")}
CONTRACTS = {
    "diversity": ([port(dims=[param("dim")])], projected("diversity", drop_dims=[param("dim")], append_dims=[{"name": "metric", "labels": param("metrics")} ])),
    "distance_matrix": ([port(dims=[param("dim")])], projected("distance", keep_dims=[param("dim")], append_dims=[PAIR_AXIS])),
    "correlation": ([port(dims=[param("dim")])], projected("correlation", keep_dims=[param("dim")], append_dims=[PAIR_AXIS])),
    "reduce": ([port(ndim=2, dims=[param("dim")])], {"mode": "choose", "param": "method", "default": "pca", "cases": {
        "pcoa": projected("scores", keep_dims=[param("dim")], append_dims=[{"name": "component"}])},
        "otherwise": projected("scores", drop_dims=[param("dim")], append_dims=[{"name": "component"}])}),
    "join": ([port(ndim=2, dims=[param("dim")]), port(ndim=2, dims=[param("dim")])],
             projected("joined", labels_unknown=True, axis_info_unknown=True)),
    "aggregate": ([port(ndim=2, dims=[param("dim")]), {**port(ndim=2, dims=[param("dim")]), "labels_axis": [{"axis": 1, "values": [param("group_col")]}]}],
                  projected("aggregate", drop_dims=[param("dim")], prepend_dims=[{"input_axis": [1, 1]}])),
    "permanova": ([port(ndim=2, dims=[param("dist_dim", "sample"), {"param": "dist_dim", "default": "sample", "suffix": "_b"}]),
                   {**port(ndim=2, dims=[param("group_dim", param("dist_dim", "sample"))]), "labels_axis": [{"axis": 1, "values": [param("group_label")]}]}],
                  {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "dims": ["comparison", "statistic"],
                   "labels": {"comparison": None, "statistic": ["F", "R2", "P", "n_perm"]}, "axis_info": {},
                   "info": {"missing_code": MISSING, "representation": {"type": "string", "const": "permanova"}}}}),
    "barplot": ([port(ndim=2, dims=[param("dim"), param("sample_dim")])], {"mode": "report"}),
}


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
