# src/task/step/steps/compare_groups.py
"""Compare two groups along one dimension of a 2D form.

Splits samples into two groups using a label column from a second
form, then runs a classical statistical test on each slice along
``dim``.

Domain-agnostic. All statistical work is delegated to classical
libraries:

    ttest        scipy.stats.ttest_ind
    welch        scipy.stats.ttest_ind(equal_var=False)
    mannwhitney  scipy.stats.mannwhitneyu
    deseq2       pydeseq2 (negative binomial GLM)

For ``method="deseq2"`` the input must be raw integer counts;
DESeq2 performs its own normalization. For the other methods the
input is used as-is.

Output
------
    dims   = [dim, "statistic"]
    labels = {dim: features,
              "statistic": {log2FC, mean_a, mean_b, stat, P, N}
                           plus Q_VALUE when method="deseq2"}
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.core.forms.metadata import project_metadata


_STAT_LABELS = {
    "log2FC": 0, "mean_a": 1, "mean_b": 2,
    "stat": 3, "P": 4, "N": 5,
}
_METHODS = ("ttest", "welch", "mannwhitney", "deseq2")


class CompareGroupsStep(Step):
    """Two-group comparison along one dimension."""

    name = "compare_groups"
    inputs_arity = 2
    outputs = []
    input_contracts = [port(ndim=2, dims=[param("dim"), param("group_dim")]), {**port(ndim=2, dims=[param("group_dim")]), "labels_any": [param("group_label")]}]
    output_contract = {"mode": "compare_groups"}
    output_parameter = "output"

    def run(self, ctx: Context, inputs) -> None:
        data_form, meta_form = inputs
        dim = ctx.step_params.get("dim")
        group_dim = ctx.step_params.get("group_dim")
        group_label = ctx.step_params.get("group_label")
        group_a = ctx.step_params.get("group_a")
        group_b = ctx.step_params.get("group_b")
        method = ctx.step_params.get("method", "ttest")
        out_name = ctx.step_params.get("output", self.name)

        for k, v in (
            ("dim", dim), ("group_dim", group_dim),
            ("group_label", group_label),
            ("group_a", group_a), ("group_b", group_b),
        ):
            if v is None:
                raise StepError(f"compare_groups: '{k}' is required")
        if method not in _METHODS:
            raise StepError(
                f"compare_groups: method must be one of {_METHODS}, "
                f"got {method!r}"
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

        codes = _resolve_groups(
            meta_form, meta_sub, group_dim, group_label,
            group_a, group_b,
        )
        mask_a = codes == 0
        mask_b = codes == 1
        n_a = int(mask_a.sum())
        n_b = int(mask_b.sum())
        if n_a < 2 or n_b < 2:
            raise StepError(
                f"compare_groups: need >= 2 samples per group, "
                f"got {n_a} and {n_b}."
            )

        feat_pos = data_form.dims.index(dim)
        moved = np.moveaxis(data_sub, feat_pos, 0)
        n_features = moved.shape[0]
        flat = moved.reshape(n_features, -1).astype(np.float64)

        missing_code = data_form.info.get("missing_code", np.nan)
        if missing_code is not None and np.isfinite(missing_code):
            flat[flat == missing_code] = np.nan

        result, extra_labels = _dispatch(method, flat, mask_a, mask_b)

        pos_to_label = {v: k for k, v in data_form.labels[dim].items()}
        stat_labels = dict(_STAT_LABELS)
        stat_labels.update(extra_labels)

        info, axis_info = project_metadata(data_form, keep_dims=[dim], derived=True)
        info.update(missing_code=np.nan, representation="comparison")
        ctx[out_name] = Form(
            data=result.astype(np.float32),
            dims=[dim, "statistic"],
            labels={
                dim: {pos_to_label[i]: i for i in range(n_features)},
                "statistic": stat_labels,
            },
            info=info,
            axis_info=axis_info,
        )

        n_tested = int(np.isfinite(result[:, 4]).sum())

        extra_keys = list(extra_labels.keys())
        per_row = []
        for i in range(n_features):
            label = pos_to_label[i]
            p = result[i, 4]
            lfc = result[i, 0]
            row = {
                "label": label,
                "log2FC": _safe_float(result[i, 0]),
                "mean_a": _safe_float(result[i, 1]),
                "mean_b": _safe_float(result[i, 2]),
                "stat": _safe_float(result[i, 3]),
                "p": _safe_float(p),
                "n": int(result[i, 5]) if np.isfinite(result[i, 5]) else 0,
            }
            for key in extra_keys:
                pos = extra_labels[key]
                row[key] = _safe_float(result[i, pos])
            per_row.append(row)

        # Order of the extra column positions, for convenience.
        extra_order = {
            key: extra_labels[key] for key in extra_keys
        }

        self._export_data = {
            "method": method,
            "dim": dim,
            "group_dim": group_dim,
            "group_label": group_label,
            "group_a": group_a,
            "group_b": group_b,
            "n_samples": len(common),
            "n_a": n_a,
            "n_b": n_b,
            "n_features": n_features,
            "n_tested": n_tested,
            "n_failed": int(n_features - n_tested),
            "statistic_columns": {
                **{k: v for k, v in _STAT_LABELS.items()},
                **extra_order,
            },
            "results": per_row,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "n_a": n_a,
            "n_b": n_b,
            "n_tested": n_tested,
        }
        print(
            f"[compare_groups] method='{method}' dim='{dim}' "
            f"a='{group_a}'(n={n_a}) b='{group_b}'(n={n_b}) "
            f"tested {n_tested}/{n_features}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _resolve_groups(meta_form, meta_sub, group_dim, group_label,
                    group_a, group_b):
    other = [d for d in meta_form.dims if d != group_dim]
    if len(other) != 1:
        raise StepError(
            f"compare_groups: meta must be 2D with '{group_dim}' plus "
            f"one other dim, got {meta_form.dims}"
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
        raise StepError("compare_groups: group_a and group_b overlap")
    if not a_mask.any() or not b_mask.any():
        raise StepError(
            f"compare_groups: group_a '{group_a}' selected "
            f"{int(a_mask.sum())} samples, group_b '{group_b}' "
            f"selected {int(b_mask.sum())}."
        )
    codes = np.full(col.shape, -1, dtype=int)
    codes[a_mask] = 0
    codes[b_mask] = 1
    return codes


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


def _dispatch(method, flat, mask_a, mask_b):
    if method in ("ttest", "welch", "mannwhitney"):
        return _scipy_test(method, flat, mask_a, mask_b), {}
    if method == "deseq2":
        return _deseq2_test(flat, mask_a, mask_b)
    raise StepError(f"compare_groups: no implementation for {method!r}")


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
        else:
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
