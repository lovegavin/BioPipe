# src/task/step/steps/hwe.py
"""Hardy-Weinberg equilibrium filter.

Reference
---------
Wigginton JE, Cutler DJ, Abecasis GR (2005).
A note on exact tests of Hardy-Weinberg equilibrium.
Am J Hum Genet 76(5):887-93.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class HweStep(Step):
    """Filter positions along one dimension by HWE p-value.

    Params:
        dim       : dimension to test along
        threshold : minimum allowed p-value
        output    : context key for the result
    """

    name = "hwe"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        threshold = float(ctx.step_params.get("threshold", 1e-6))
        out_name = ctx.step_params.get("output", self.name)

        for field in ("missing_code", "ploidy"):
            if field not in form.info:
                raise StepError(
                    f"Form has no info['{field}']. "
                    f"Available: {sorted(form.info)}"
                )
        ploidy = int(form.info["ploidy"])
        if ploidy != 2:
            raise StepError(
                f"HWE exact test requires ploidy == 2, got {ploidy}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' is not present. Available: {form.dims}"
            )

        axis = form.dims.index(dim)
        other_axes = tuple(i for i in range(form.data.ndim) if i != axis)

        missing_code = form.info["missing_code"]
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(form.data)
        else:
            missing = form.data == missing_code

        valid = ~missing
        n_hom_ref = (valid & (form.data == 0)).sum(axis=other_axes)
        n_het     = (valid & (form.data == 1)).sum(axis=other_axes)
        n_hom_alt = (valid & (form.data == 2)).sum(axis=other_axes)

        n_positions = form.data.shape[axis]
        pvals = np.full(n_positions, np.nan, dtype=float)
        for i in range(n_positions):
            pvals[i] = _hwe_exact(
                int(n_hom_ref[i]), int(n_het[i]), int(n_hom_alt[i])
            )

        with np.errstate(invalid="ignore"):
            keep = (~np.isnan(pvals)) & (pvals >= threshold)

        n_before = form.data.shape[axis]
        n_after = int(keep.sum())
        if n_after == 0:
            raise StepError(
                f"hwe: threshold removed every position along '{dim}'"
            )

        kept = np.where(keep)[0]
        new_form = form.subset_axis(dim, kept)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        pvalues_by_label = {
            pos_to_label[i]: (
                float(pvals[i]) if np.isfinite(pvals[i]) else None
            )
            for i in range(n_before)
        }
        pvalues_kept_by_label = {
            pos_to_label[int(i)]: float(pvals[i]) for i in kept
        }

        self._export_data = {
            "dim": dim,
            "threshold": threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
            "pvalues_by_label": pvalues_by_label,
            "pvalues_kept_by_label": pvalues_kept_by_label,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "threshold": threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
        }

        print(
            f"[hwe] dim='{dim}' {n_before} -> {n_after} "
            f"(threshold={threshold})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _hwe_exact(n_hom_ref: int, n_het: int, n_hom_alt: int) -> float:
    n_total = n_hom_ref + n_het + n_hom_alt
    if n_total == 0:
        return np.nan

    obs_homc = min(n_hom_ref, n_hom_alt)
    obs_homr = max(n_hom_ref, n_hom_alt)
    obs_hets = n_het

    rare_copies = 2 * obs_homc + obs_hets
    genotypes = obs_hets + obs_homr + obs_homc
    if rare_copies == 0:
        return 1.0

    probs = np.zeros(rare_copies + 1, dtype=float)
    mid = int(rare_copies * (2 * genotypes - rare_copies) / (2 * genotypes))
    if (mid - rare_copies) % 2 != 0:
        mid += 1
    probs[mid] = 1.0
    total = 1.0

    curr_hets = mid
    curr_homr = (rare_copies - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets > 1:
        probs[curr_hets - 2] = (
            probs[curr_hets] * curr_hets * (curr_hets - 1)
            / (4.0 * (curr_homr + 1) * (curr_homc + 1))
        )
        total += probs[curr_hets - 2]
        curr_homr += 1
        curr_homc += 1
        curr_hets -= 2

    curr_hets = mid
    curr_homr = (rare_copies - mid) // 2
    curr_homc = genotypes - curr_hets - curr_homr
    while curr_hets <= rare_copies - 2:
        probs[curr_hets + 2] = (
            probs[curr_hets] * 4.0 * curr_homr * curr_homc
            / ((curr_hets + 2) * (curr_hets + 1))
        )
        total += probs[curr_hets + 2]
        curr_homr -= 1
        curr_homc -= 1
        curr_hets += 2

    probs /= total
    return float(min(probs[probs <= probs[obs_hets]].sum(), 1.0))