"""Linear lifetime construction, heap eviction and analytical resource estimates.

Planning is heuristic. The number of choices per boundary is bounded; no cache
subsets are enumerated. Sources and overwritten aliases have distinct versions.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict

FORM_STEPS = frozenset({"select", "drop", "transpose", "rename_dim", "attach_info",
                        "missing", "maf", "hwe", "ld_prune", "pca", "concat",
                        "regress", "correction"})
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
    profile = profiles.get(name, {})
    return (int(profile.get("workspace_mb", workspace / 1024**2) * 1024**2),
            int(profile.get("output_mb", output / 1024**2) * 1024**2))


def block_elements(headroom: int, dtype, preferred_bytes: int, multiplier: int = 4) -> int:
    """Chunk + finite selection + float64 statistics buffers fit the reservation."""
    bytes_per_element = max(dtype.itemsize, 8) * multiplier + 1
    return max(0, min(preferred_bytes // max(dtype.itemsize, 1), headroom // bytes_per_element))
