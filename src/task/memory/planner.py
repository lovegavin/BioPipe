"""Linear lifetime construction, heap eviction and analytical resource estimates.

Planning is heuristic. The number of choices per boundary is bounded; no cache
subsets are enumerated. Sources and overwritten aliases have distinct versions.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict

FORM_STEPS = frozenset({"select", "drop", "transpose", "rename_dim", "attach_info",
                        "missing", "maf", "hwe", "ld_prune", "pca", "concat",
                        "regress", "correction", "filter_min", "normalize", "log_transform", "impute",
                        "compare_groups", "logrank_test", "cox_regression"})
NEVER = 10**18


class LifetimePlan:
    def __init__(self, steps: list[dict], registry: dict):
        self.uses = defaultdict(list)
        self.producers = defaultdict(list)
        self.steps = steps
        for i, spec in enumerate(steps):
            for name in dict.fromkeys(spec.get("inputs", [])):
                self.uses[name].append(i)
            cls = registry.get(spec["name"])
            outputs = list(getattr(cls, "outputs", []))
            if getattr(cls, "output_parameter", None) or spec["name"] in FORM_STEPS or spec.get("params", {}).get("output"):
                outputs.append(spec.get("params", {}).get("output", spec["name"]))
            for name in dict.fromkeys(outputs):
                self.producers[name].append(i)

    def next_use(self, name: str, position: int, generated: int) -> int:
        positions = self.uses[name]
        cursor = bisect_right(positions, position)
        result = positions[cursor] if cursor < len(positions) else NEVER
        replacements = self.producers[name]
        j = bisect_right(replacements, generated)
        # A same-step input is read before that step replaces the alias.
        replacement = replacements[j] if j < len(replacements) else NEVER
        return result if result <= replacement else NEVER


def full_estimate(name: str, forms: list, params: dict, profiles: dict) -> tuple[int, int]:
    """Return estimated additional workspace and output bytes, not a hard bound."""
    from src.core.files import FileArtifact
    if any(isinstance(form, FileArtifact) for form in forms):
        # File-aware operators override this hook. For incompatible connections,
        # leave allocation at zero so contract validation supplies the error.
        return 0, 0
    data = sum(f.data.nbytes for f in forms)
    metadata = sum(sum(len(v) for v in f.labels.values()) * 96 for f in forms)
    workspace = 2 * data
    output = data + metadata if name in FORM_STEPS or params.get("output") else 0
    if name == "pca" and forms:
        form = forms[0]
        workspace = 96 * form.data.size + 16 * sum(form.data.shape)
        axis = form.dims.index(params["dim"]) if params.get("dim") in form.dims else 0
        observations = form.data.shape[1 - axis] if form.data.ndim == 2 else 0
        components = max(0, min(int(params.get("n_components", 10)), min(form.data.shape)))
        output = 4 * observations * components + 96 * (observations + components)
    elif name == "describe":
        workspace = 3 * data
    elif name in {"rename_dim", "transpose"}:
        workspace = data
    elif name in {"normalize", "log_transform", "impute", "filter_min"} and forms:
        # Float64 working arrays, masks, quantile indices, and report summaries.
        # These kernels do not offer equivalent streaming implementations yet.
        cells = forms[0].data.size
        workspace = cells * (80 if name == "normalize" else 56) + metadata * 2
        output = cells * 4 + metadata
    elif name == "compare_groups" and forms:
        form = forms[0]
        axis = form.dims.index(params["dim"]) if params.get("dim") in form.dims else 0
        features = form.data.shape[axis]
        workspace = 96 * form.data.size + metadata * 2
        if params.get("method") == "deseq2":
            workspace = max(workspace * 4, 256 * 1024**2)
        output = features * 7 * 4 + (features + 7) * 96 + metadata
    elif name in {"cox_regression", "logrank_test", "kaplan_meier"} and forms:
        rows, columns = forms[0].data.shape
        # Cox may one-hot encode every categorical value. Bound the design width
        # conservatively using sample count when categorical covariates are used.
        width = min(rows, columns + rows * len(params.get("categorical", [])))
        workspace = max(data * 12 + rows * width * 32 + width * width * 32, 16 * 1024**2)
        groups = params.get("groups")
        if groups:
            group_count = len(groups)
        elif params.get("group_label") in forms[0].labels.get(forms[0].dims[1], {}):
            import numpy as np
            column = forms[0].labels[forms[0].dims[1]][params["group_label"]]
            group_count = len(np.unique(forms[0].data[:, column]))
        else:
            group_count = rows
        comparisons = 1 + group_count * (group_count - 1) // 2 if params.get("pairwise") else 1
        output = (width * 7 if name == "cox_regression" else comparisons * 3) * 100 if name in FORM_STEPS else 0
    elif name == "heatmap" and forms:
        rows, columns = forms[0].data.shape
        selected = min(max(rows, columns), int(params.get("top_n", 50))) if params.get("select", "variance") == "variance" else max(rows, columns)
        workspace = 64 * forms[0].data.size + 16 * (selected**2 + min(rows, columns)**2)
    elif name in {"volcano", "ma_plot", "boxplot", "forest_plot"}:
        workspace = max(16 * data + metadata, 8 * 1024**2)
    profile = profiles.get(name, {})
    return (int(profile.get("workspace_mb", workspace / 1024**2) * 1024**2),
            int(profile.get("output_mb", output / 1024**2) * 1024**2))


def block_elements(headroom: int, dtype, preferred_bytes: int, multiplier: int = 4) -> int:
    """Chunk + finite selection + float64 statistics buffers fit the reservation."""
    bytes_per_element = max(dtype.itemsize, 8) * multiplier + 1
    return max(0, min(preferred_bytes // max(dtype.itemsize, 1), headroom // bytes_per_element))
