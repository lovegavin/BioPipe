"""SDK declarations for the upstream axis and single-cell building blocks.

These kernels use full-memory admission. Only Readers and operators explicitly
advertising a streaming protocol may run in chunks.
"""
from src.core.contracts import param, port
from ._microbiome import DIM, enum, estimate, field, projected, schema, strings

STATISTICS = ["sum", "mean", "std", "var", "min", "max", "median", "nonzero", "count"]
SCHEMAS = {
    "bin": schema({"dim": DIM, "bins": field("integer", minimum=1, default=10),
        "method": enum(["quantile", "uniform"], "quantile"), "value_label": DIM,
        "stat": enum(["mean", "median", "min", "max", "first"], "mean")}, ["dim"]),
    "cluster_axis": schema({"dim": DIM, "method": enum(["kmeans", "hierarchical", "louvain"]),
        "n_clusters": field("integer", minimum=1), "n_neighbors": field("integer", minimum=1, default=15),
        "resolution": field("number", exclusiveMinimum=0, default=1.0), "random_state": field("integer", default=0)}, ["dim", "method"]),
    "filter_by": schema({"dim": DIM, "rules": field("array", minItems=1, items={
        **schema({"field": DIM, "min": field("number"), "max": field("number")}, ["field"]),
        "anyOf": [{"required": ["min"]}, {"required": ["max"]}]})}, ["dim", "rules"]),
    "rank_axis": {**schema({"dim": DIM, "by": enum(["variance", "std", "mean", "sum", "nonzero", "abs_mean", "max"]),
        "top_n": field("integer", minimum=1), "min_value": field("number"),
        "keep_ties": field("boolean", default=False), "descending": field("boolean", default=True)}, ["dim", "by"]),
        "anyOf": [{"required": ["top_n"]}, {"required": ["min_value"]}]},
    "reduce_axis": schema({"dim": DIM, "stats": {"oneOf": [enum(STATISTICS),
        strings(minItems=1, uniqueItems=True, items=enum(STATISTICS))]}}, ["dim", "stats"]),
    "dotplot": schema({"feature_dim": DIM, "group_dim": DIM, "features": strings(minItems=1, uniqueItems=True),
        "group_label": DIM, "groups": strings(minItems=1, uniqueItems=True),
        "statistic": enum(["mean", "median", "sum"], "mean"), "proportion_mode": enum(["nonzero", "threshold"], "nonzero"),
        "threshold": field("number", default=0), "filename": DIM, "title": field("string"), "xlabel": field("string"),
        "ylabel": field("string"), "cmap": field("string", default="viridis"), "dot_scale": field("number", exclusiveMinimum=0, default=200)},
        ["feature_dim", "group_dim", "features", "group_label", "filename"]),
    "violin": schema({"dim": field("string", default="feature"), "value_label": DIM, "group_dim": DIM, "group_label": DIM,
        "groups": strings(minItems=1, uniqueItems=True), "filename": DIM, "title": field("string"), "xlabel": field("string"),
        "ylabel": field("string"), "inner": enum(["box", "quartile", "point", "none"], "box"),
        "show_points": field("boolean", default=False), "point_size": field("number", exclusiveMinimum=0, default=4),
        "point_alpha": field("number", minimum=0, maximum=1, default=.5), "rotate_labels": field("boolean", default=False)},
        ["value_label", "group_dim", "group_label", "filename"]),
    "compare_groups": {**schema({"dim": DIM, "group_dim": DIM, "group_label": DIM,
        "mode": enum(["two_groups", "one_vs_rest", "pairwise"], "two_groups"),
        "group_a": field(["string", "number"], **{"x-ui-type": "scalar"}), "group_b": field(["string", "number"], **{"x-ui-type": "scalar"}),
        "groups": strings(minItems=2, uniqueItems=True), "min_per_group": field("integer", minimum=1, default=2),
        "method": enum(["ttest", "welch", "mannwhitney", "wilcoxon", "deseq2"], "ttest")}, ["dim", "group_dim", "group_label"]),
        "if": {"properties": {"mode": {"const": "two_groups"}}}, "then": {"required": ["group_a", "group_b"]}},
}
CONTRACTS = {
    "bin": ([port(dims=[param("dim")])], projected("bins", keep_dims=[param("dim")], append_dims=[{"name": "bin", "labels": ["bin"]}])),
    "cluster_axis": ([port(dims=[param("dim")])], projected("clusters", keep_dims=[param("dim")], append_dims=[{"name": "cluster", "labels": ["cluster"]}])),
    "reduce_axis": ([port(dims=[param("dim")])], projected("summary", drop_dims=[param("dim")], append_dims=[{"name": "statistic", "labels": param("stats")}])),
    "filter_by": ([port(dims=[param("dim")]), port(ndim=2, dims=[param("dim"), "statistic"])], {"mode": "subset"}),
    "rank_axis": ([port(dims=[param("dim")])], {"mode": "subset"}),
    "dotplot": ([port(ndim=2, dims=[param("feature_dim"), param("group_dim")]),
        {**port(ndim=2, dims=[param("group_dim")]), "labels_any": [param("group_label")]}], {"mode": "report"}),
    "violin": ([{**port(ndim=2, dims=[param("dim", "feature"), param("group_dim")]), "labels_any": [param("value_label")]},
        {**port(ndim=2, dims=[param("group_dim")]), "labels_any": [param("group_label")]}], {"mode": "report"}),
    "compare_groups": ([port(ndim=2, dims=[param("dim"), param("group_dim")]),
        {**port(ndim=2, dims=[param("group_dim")]), "labels_any": [param("group_label")]}], {"mode": "compare_groups"}),
}


def estimate_axis(name, inputs, params, profiles):
    workspace, output = estimate(name, inputs, params, {})
    if inputs:
        form = inputs[0]
        dim = params.get("dim", params.get("group_dim"))
        n = form.data.shape[form.dims.index(dim)] if dim in form.dims else max(form.data.shape)
        if name == "cluster_axis":
            workspace += n * n * 32
        elif name == "compare_groups" and params.get("mode", "two_groups") != "two_groups":
            samples = form.data.shape[form.dims.index(params["group_dim"])]
            groups = len(params.get("groups", [])) or samples
            comparisons = groups * (groups - 1) // 2 if params["mode"] == "pairwise" else groups
            output = n * comparisons * 7 * 4 + comparisons * 512
            workspace += output * 4
        elif name in {"dotplot", "violin"}:
            workspace, output = max(workspace, 16 * 1024**2), 0
    override = profiles.get(name, {})
    return int(override.get("workspace_mb", workspace / 1024**2) * 1024**2), int(override.get("output_mb", output / 1024**2) * 1024**2)
