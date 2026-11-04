"""SDK declarations for the upstream axis and single-cell building blocks.

These kernels use full-memory admission. Only Readers and operators explicitly
advertising a streaming protocol may run in chunks.
"""
from ._microbiome import estimate

STATISTICS = ["sum", "mean", "std", "var", "min", "max", "median", "nonzero", "count"]
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
