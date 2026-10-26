# src/task/step/steps/compare_groups.py
"""Compare groups along one dimension of a 2D form.

Three modes
-----------
    two_groups     compare group_a vs group_b (default, backward
                   compatible with the original two-group API).
                   Output dims: [dim, "statistic"].
    one_vs_rest    for every group g: g vs the union of all other
                   groups. Output dims: [dim, "comparison",
                   "statistic"], with one entry per group.
    pairwise       every unordered pair (g_i, g_j). Output dims:
                   [dim, "comparison", "statistic"].

Methods
-------
    ttest        scipy.stats.ttest_ind(equal_var=True)
    welch        scipy.stats.ttest_ind(equal_var=False)
    mannwhitney  scipy.stats.mannwhitneyu
    deseq2       pydeseq2 negative binomial GLM

The two-group output is a 2D form with columns log2FC, mean_a,
mean_b, stat, P, N. The multi-group output adds a "comparison"
axis between the feature axis and the statistic axis.

Consuming a multi-group result in a 2D pipeline requires selecting
one comparison first:

    - name: select
      inputs: [result]
      params: {dim: comparison, labels: ["A"], output: result_a}

Params:
    dim          : feature dim (required)
    group_dim    : sample dim shared by both inputs (required)
    group_label  : column on the metadata's other dim (required)
    mode         : "two_groups" | "one_vs_rest" | "pairwise"
                   (default "two_groups")
    group_a      : first group (required for two_groups)
    group_b      : second group (required for two_groups)
    groups       : list of group names to compare in multi-group
                   modes (optional; if omitted, all groups present
                   in the metadata are used)
    method       : "ttest" | "welch" | "mannwhitney" | "deseq2"
                   (default "ttest")
    min_per_group: skip a comparison if either side has fewer than
                   this many samples (multi-group only, default 2)
    output       : context key for the result (default: step name)
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._axis_contracts import estimate_axis
from ._microbiome import metadata
from ._axis_contracts import estimate_axis
from ._microbiome import metadata


_METHODS = (
    "ttest", "welch",
    "mannwhitney", "wilcoxon",   # same test, two names
    "deseq2",
)
_MODES = ("two_groups", "one_vs_rest", "pairwise")

_STAT_LABELS = {
    "log2FC": 0, "mean_a": 1, "mean_b": 2,
    "stat": 3, "P": 4, "N": 5,
}


class CompareGroupsStep(Step):
    """Compare groups along one dimension."""
    provider = 'biopipe-expression'
    parameters_file = 'compare_groups.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'compare_groups',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Group comparison',
     'description': 'T-test、Welch、Mann–Whitney 或 DESeq2',
     'category': 'Analysis',
     'icon': 'Intersect',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None},
                                        {'param': 'group_dim', 'default': None}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'group_dim', 'default': None}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2,
                               'labels_any': [{'param': 'group_label', 'default': None}]}],
                   'output': {'mode': 'compare_groups'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['pydeseq2==0.5.4'],
     'dependency_imports': ['pydeseq2'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output'}




    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate_axis(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        data_form, meta_form = inputs
        dim = ctx.step_params.get("dim")
        group_dim = ctx.step_params.get("group_dim")
        group_label = ctx.step_params.get("group_label")
        mode = ctx.step_params.get("mode", "two_groups")
        method = ctx.step_params.get("method", "ttest")
        out_name = ctx.step_params.get("output", self.name)

        for k, v in (
            ("dim", dim), ("group_dim", group_dim),
            ("group_label", group_label),
        ):
            if not v:
                raise StepError(f"compare_groups: '{k}' is required")
        if mode not in _MODES:
            raise StepError(
                f"compare_groups: mode must be one of {list(_MODES)}, "
                f"got {mode!r}"
            )
        if method not in _METHODS:
            raise StepError(
                f"compare_groups: method must be one of "
                f"{list(_METHODS)}, got {method!r}"
            )
        for form, label in ((data_form, "data"), (meta_form, "meta")):
            if group_dim not in form.dims:
                raise StepError(
                    f"compare_groups: group_dim '{group_dim}' not in "
                    f"{label}. Available: {form.dims}"
                )
        if dim not in data_form.dims:
            raise StepError(
                f"compare_groups: dim '{dim}' not in data. "
                f"Available: {data_form.dims}"
            )

        common, data_sub, meta_sub = _align_samples(
            data_form, meta_form, group_dim
        )

        feat_pos = data_form.dims.index(dim)
        moved = np.moveaxis(data_sub, feat_pos, 0)
        n_features = moved.shape[0]
        flat = moved.reshape(n_features, -1).astype(np.float64)

        if mode == "two_groups":
            self._run_two_groups(
                ctx, out_name, data_form, meta_form, meta_sub,
                group_dim, group_label, dim, method,
                n_features, flat,
            )
        else:
            self._run_many_groups(
                ctx, out_name, data_form, meta_form, meta_sub,
                group_dim, group_label, dim, mode, method,
                ctx.step_params.get("groups"),
                int(ctx.step_params.get("min_per_group", 2)),
                n_features, flat,
            )

    # ------------------------------------------------------------------ #
    # Two-group mode
    # ------------------------------------------------------------------ #

    def _run_two_groups(
        self, ctx, out_name, data_form, meta_form, meta_sub,
        group_dim, group_label, dim, method,
        n_features, flat,
    ) -> None:
        group_a = ctx.step_params.get("group_a")
        group_b = ctx.step_params.get("group_b")
        if group_a is None or group_b is None:
            raise StepError(
                "compare_groups (two_groups): 'group_a' and 'group_b' "
                "are required"
            )

        mask_a, mask_b = _resolve_two_groups(
            meta_form, meta_sub, group_dim, group_label,
            group_a, group_b,
        )
        n_a = int(mask_a.sum())
        n_b = int(mask_b.sum())
        if n_a < 2 or n_b < 2:
            raise StepError(
                f"compare_groups: need >= 2 samples per group, "
                f"got {n_a} and {n_b}."
            )

        if method == "deseq2":
            block, extra = _deseq2_test(flat, mask_a, mask_b)
            stat_labels = dict(_STAT_LABELS)
            stat_labels.update(extra)
        else:
            block = _scipy_test(method, flat, mask_a, mask_b)
            stat_labels = dict(_STAT_LABELS)

        pos_to_feature = {
            v: k for k, v in data_form.labels[dim].items()
        }
        info, axes = metadata(data_form, [dim], "comparison")
        info, axes = metadata(data_form, [dim], "comparison")
        ctx[out_name] = Form(
            data=block.astype(np.float32),
            dims=[dim, "statistic"],
            labels={
                dim: {pos_to_feature[i]: i for i in range(n_features)},
                "statistic": stat_labels,
            },
            info=info, axis_info=axes,
        )

        n_tested = int(np.isfinite(block[:, 4]).sum())

        pos_to_label = {
            v: k for k, v in data_form.labels[dim].items()
        }
        stat_keys = list(stat_labels.keys())
        results = []
        for i in range(n_features):
            row = {"label": pos_to_label.get(i, f"#{i}")}
            for col_idx, key in enumerate(stat_keys):
                v = block[i, col_idx]
                row[key] = float(v) if np.isfinite(v) else None
            results.append(row)

        self._export_data = {
            "mode": "two_groups",
            "method": method,
            "dim": dim,
            "group_dim": group_dim,
            "group_label": group_label,
            "group_a": group_a,
            "group_b": group_b,
            "n_a": n_a,
            "n_b": n_b,
            "n_features": n_features,
            "n_tested": n_tested,
            "statistics": stat_keys,
            "results": results,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "mode": "two_groups",
            "method": method,
            "n_a": n_a,
            "n_b": n_b,
            "n_tested": n_tested,
        }
        print(
            f"[compare_groups] mode='two_groups' method='{method}' "
            f"dim='{dim}' a='{group_a}'(n={n_a}) b='{group_b}'(n={n_b}) "
            f"tested {n_tested}/{n_features}"
        )

    # ------------------------------------------------------------------ #
    # Multi-group mode
    # ------------------------------------------------------------------ #

    def _run_many_groups(
        self, ctx, out_name, data_form, meta_form, meta_sub,
        group_dim, group_label, dim, mode, method,
        groups_arg, min_per_group,
        n_features, flat,
    ) -> None:
        if min_per_group < 1:
            raise StepError(
                f"compare_groups: min_per_group must be >= 1, "
                f"got {min_per_group}"
            )

        sample_groups = _decode_group_column(
            meta_form, meta_sub, group_dim, group_label
        )
        if sample_groups is None:
            raise StepError(
                f"compare_groups: group_label '{group_label}' not "
                f"found on metadata"
            )
        if not any(g is not None for g in sample_groups):
            raise StepError(
                "compare_groups: no samples with a valid group value"
            )

        all_groups = sorted({g for g in sample_groups if g is not None})
        if groups_arg is not None:
            if not isinstance(groups_arg, list) or not groups_arg:
                raise StepError(
                    "compare_groups: 'groups' must be a non-empty list"
                )
            groups_arg = [str(g) for g in groups_arg]
            missing = [g for g in groups_arg if g not in all_groups]
            if missing:
                raise StepError(
                    f"compare_groups: groups not found: {missing}. "
                    f"Available: {all_groups}"
                )
            group_list = list(groups_arg)
        else:
            group_list = all_groups

        if mode == "one_vs_rest":
            comparison_defs = [(g, None) for g in group_list]
        else:  # pairwise
            comparison_defs = [
                (a, b) for a, b in combinations(group_list, 2)
            ]
        if not comparison_defs:
            raise StepError(
                "compare_groups: no comparisons to run"
            )

        use_deseq2 = method == "deseq2"
        n_stat = 7 if use_deseq2 else 6

        # Collect only the successful comparisons; then assemble a
        # compact 3D array so the "comparison" dim has no unlabeled
        # positions.
        successful: list[tuple[str, np.ndarray]] = []
        skipped: list[dict] = []

        for a, b in comparison_defs:
            mask_a = np.array(
                [g == a for g in sample_groups], dtype=bool
            )
            if b is None:
                mask_b = np.array(
                    [g is not None and g != a for g in sample_groups],
                    dtype=bool,
                )
                label = a
            else:
                mask_b = np.array(
                    [g == b for g in sample_groups], dtype=bool
                )
                label = f"{a}_vs_{b}"

            n_a = int(mask_a.sum())
            n_b = int(mask_b.sum())
            if n_a < min_per_group or n_b < min_per_group:
                skipped.append({
                    "comparison": label,
                    "n_a": n_a,
                    "n_b": n_b,
                    "reason": (
                        f"needs at least {min_per_group} per side"
                    ),
                })
                continue

            if use_deseq2:
                block, _ = _deseq2_test(flat, mask_a, mask_b)
            else:
                block = _scipy_test(method, flat, mask_a, mask_b)

            successful.append((label, block))

        if not successful:
            raise StepError(
                "compare_groups: every comparison was skipped "
                f"(min_per_group={min_per_group})."
            )

        n_comp = len(successful)
        results = np.full(
            (n_features, n_comp, n_stat), np.nan, dtype=np.float64
        )
        comparison_labels: dict[str, int] = {}
        for ci, (label, block) in enumerate(successful):
            results[:, ci, :block.shape[1]] = block
            comparison_labels[label] = ci

        pos_to_feature = {
            v: k for k, v in data_form.labels[dim].items()
        }
        stat_labels = dict(_STAT_LABELS)
        if use_deseq2:
            stat_labels["Q_VALUE"] = 6

        info, axes = metadata(data_form, [dim], "comparison")
        info, axes = metadata(data_form, [dim], "comparison")
        ctx[out_name] = Form(
            data=results.astype(np.float32),
            dims=[dim, "comparison", "statistic"],
            labels={
                dim: {pos_to_feature[i]: i for i in range(n_features)},
                "comparison": comparison_labels,
                "statistic": stat_labels,
            },
            info=info, axis_info=axes,
        )

        stat_keys = list(stat_labels.keys())
        results_by_comparison: dict[str, list[dict]] = {}
        for label, ci in comparison_labels.items():
            block = results[:, ci, :]
            per_feature = []
            for i in range(n_features):
                row = {"label": pos_to_feature[i]}
                for col_idx, key in enumerate(stat_keys):
                    v = block[i, col_idx]
                    row[key] = float(v) if np.isfinite(v) else None
                per_feature.append(row)
            results_by_comparison[label] = per_feature

        self._export_data = {
            "mode": mode,
            "method": method,
            "dim": dim,
            "group_dim": group_dim,
            "group_label": group_label,
            "n_features": n_features,
            "n_comparisons": len(comparison_labels),
            "n_skipped": len(skipped),
            "comparisons": list(comparison_labels.keys()),
            "statistics": stat_keys,
            "skipped": skipped,
            "groups": group_list,
            "results": results_by_comparison,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "mode": mode,
            "method": method,
            "n_comparisons": len(comparison_labels),
            "n_skipped": len(skipped),
        }
        print(
            f"[compare_groups] mode='{mode}' method='{method}' "
            f"dim='{dim}' comparisons={len(comparison_labels)} "
            f"features={n_features}"
            + (f" skipped={len(skipped)}" if skipped else "")
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


# ------------------------------------------------------------------ #
# Shared helpers
# ------------------------------------------------------------------ #

def _align_samples(data_form, meta_form, group_dim):
    common = [
        s for s in data_form.labels[group_dim]
        if s in meta_form.labels[group_dim]
    ]
    if len(common) < 4:
        raise StepError(
            f"compare_groups: only {len(common)} common samples "
            f"on '{group_dim}'."
        )
    data_idx = [data_form.labels[group_dim][s] for s in common]
    meta_idx = [meta_form.labels[group_dim][s] for s in common]
    data_sub = np.take(
        data_form.data, data_idx,
        axis=data_form.dims.index(group_dim),
    )
    meta_sub = np.take(
        meta_form.data, meta_idx,
        axis=meta_form.dims.index(group_dim),
    )
    return common, data_sub, meta_sub


def _resolve_two_groups(meta_form, meta_sub, group_dim, group_label,
                        group_a, group_b):
    other = [d for d in meta_form.dims if d != group_dim]
    if len(other) != 1:
        raise StepError(
            f"compare_groups: metadata must be 2D with '{group_dim}' "
            f"plus one other dim, got {meta_form.dims}"
        )
    other = other[0]
    if group_label not in meta_form.labels.get(other, {}):
        raise StepError(
            f"compare_groups: group_label '{group_label}' not in "
            f"'{other}'. Available: "
            f"{sorted(meta_form.labels.get(other, {}))}"
        )
    col = np.take(
        meta_sub,
        meta_form.labels[other][group_label],
        axis=meta_form.dims.index(other),
    )
    encoders = meta_form.info.get("encoders", {})
    if other in encoders and group_label in encoders[other]:
        emap = encoders[other][group_label].mapping
        group_a = _to_code(group_a, emap, "group_a")
        group_b = _to_code(group_b, emap, "group_b")

    a_mask = col == group_a
    b_mask = col == group_b
    if (a_mask & b_mask).any():
        raise StepError(
            "compare_groups: group_a and group_b overlap"
        )
    if not a_mask.any() or not b_mask.any():
        raise StepError(
            f"compare_groups: group_a '{group_a}' selected "
            f"{int(a_mask.sum())} samples, group_b '{group_b}' "
            f"selected {int(b_mask.sum())}."
        )
    return a_mask, b_mask


def _to_code(name, mapping, which):
    if name in mapping:
        return mapping[name]
    try:
        return int(name)
    except (TypeError, ValueError):
        raise StepError(
            f"compare_groups: {which}='{name}' not in encoder mapping "
            f"and not an integer. Known: {sorted(mapping)}"
        )


def _decode_group_column(meta_form, meta_sub, group_dim, group_label):
    other_dims = [d for d in meta_form.dims if d != group_dim]
    if len(other_dims) != 1:
        return None
    other = other_dims[0]
    if group_label not in meta_form.labels.get(other, {}):
        return None
    col_pos = meta_form.labels[other][group_label]
    col_axis = meta_form.dims.index(other)
    col = np.take(meta_sub, col_pos, axis=col_axis)

    encoders = meta_form.info.get("encoders", {})
    encoder = None
    if other in encoders and group_label in encoders[other]:
        encoder = encoders[other][group_label]

    out: list[str | None] = []
    for v in col:
        if not np.isfinite(v):
            out.append(None)
            continue
        if encoder is not None:
            try:
                out.append(str(encoder.inverse[int(v)]))
            except (KeyError, ValueError, TypeError):
                out.append(None)
            continue
        f = float(v)
        out.append(str(int(f)) if f.is_integer() else str(f))
    return out


def _scipy_test(method, flat, mask_a, mask_b):
    n_features = flat.shape[0]
    result = np.full((n_features, 6), np.nan, dtype=np.float64)
    for i in range(n_features):
        ya = flat[i, mask_a]
        yb = flat[i, mask_b]
        ya = ya[np.isfinite(ya)]
        yb = yb[np.isfinite(yb)]
        if ya.size < 2 or yb.size < 2:
            continue
        if method == "ttest":
            stat, p = stats.ttest_ind(yb, ya, equal_var=True)
        elif method == "welch":
            stat, p = stats.ttest_ind(yb, ya, equal_var=False)
        else:  # mannwhitney or wilcoxon
            try:
                stat, p = stats.mannwhitneyu(
                    yb, ya, alternative="two-sided"
                )
            except ValueError:
                continue
        if not (np.isfinite(stat) and np.isfinite(p)):
            continue
        result[i] = [
            float(np.log2((yb.mean() + 0.5) / (ya.mean() + 0.5))),
            float(ya.mean()),
            float(yb.mean()),
            float(stat),
            float(p),
            int(ya.size + yb.size),
        ]
    return result


def _deseq2_test(flat, mask_a, mask_b):
    try:
        import pandas as pd
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats
    except ImportError as exc:
        raise StepError(
            "compare_groups/deseq2: pydeseq2 is required. "
            "Install with: pip install pydeseq2"
        ) from exc

    # Other metadata groups must never silently enter group B. DESeq2 needs
    # raw integer counts; rounding normalized data would change the analysis.
    selected = mask_a | mask_b
    flat = flat[:, selected]
    mask_a, mask_b = mask_a[selected], mask_b[selected]
    if not np.isfinite(flat).all() or (flat < 0).any() or not np.equal(flat, np.rint(flat)).all():
        raise StepError("compare_groups/deseq2: use finite, non-negative raw integer counts before normalization or log transformation")
    n_features, n_samples = flat.shape
    counts = pd.DataFrame(
        np.rint(flat).astype(int).T,
        columns=[f"g{i}" for i in range(n_features)],
        index=[f"s{j}" for j in range(n_samples)],
    )
    meta = pd.DataFrame(
        {"group": ["A" if mask_a[j] else "B"
                   for j in range(n_samples)]},
        index=counts.index,
    )

    dds = DeseqDataSet(
        counts=counts,
        metadata=meta,
        design="~group",
        n_cpus=1,
        quiet=True,
    )
    dds.deseq2()

    stat_res = DeseqStats(dds, contrast=["group", "B", "A"], n_cpus=1, quiet=True)
    stat_res.summary()
    res = stat_res.results_df

    log2fc = res["log2FoldChange"].to_numpy()
    statv = res["stat"].to_numpy()
    pval = res["pvalue"].to_numpy()
    padj = res["padj"].to_numpy()

    mean_a = flat[:, mask_a].mean(axis=1)
    mean_b = flat[:, mask_b].mean(axis=1)
    n = np.full(n_features, n_samples, dtype=float)

    result = np.full((n_features, 7), np.nan, dtype=np.float64)
    result[:, 0] = log2fc
    result[:, 1] = mean_a
    result[:, 2] = mean_b
    result[:, 3] = statv
    result[:, 4] = pval
    result[:, 5] = n
    result[:, 6] = padj

    return result, {"Q_VALUE": 6}

def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None
