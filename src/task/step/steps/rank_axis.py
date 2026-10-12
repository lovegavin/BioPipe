# src/task/step/steps/rank_axis.py
"""Rank positions along one axis by a statistic and keep the top N.

For each position along ``dim``, computes a ranking statistic over
the other axes, then returns a subset of the input form containing
only the selected positions.

Selection
---------
``top_n``      keep the N highest-ranked positions
``min_value``  keep positions whose statistic is >= the threshold
               (or <= when ``descending=False``)

When both are given, the selection is their **intersection**: a
position must be in the top N **and** satisfy the threshold.

Ranking statistics
------------------
    variance     variance across the other axes
    std          standard deviation
    mean         mean across the other axes
    sum          sum across the other axes
    nonzero      number of non-zero values
    abs_mean     mean of absolute values
    max          maximum value

Missing cells are excluded from every statistic.

Ties
----
When several positions share the same statistic value, they are
ordered by their original label order. If ``keep_ties`` is True and
a tie straddles the top-N cutoff, all tied positions are kept and
the result may exceed ``top_n``. If False (default), exactly
``top_n`` positions are kept.

Params:
    dim         : dimension to rank (required)
    by          : statistic name (required)
    top_n       : how many positions to keep
    min_value   : threshold on the statistic
    keep_ties   : keep all tied positions at the top-N cutoff
                  (default False)
    descending  : rank from largest to smallest (default True)
    output      : context key for the result (default: step name)

At least one of ``top_n`` or ``min_value`` is required.
"""

from __future__ import annotations

import warnings

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_STATS = (
    "variance", "std", "mean", "sum",
    "nonzero", "abs_mean", "max",
)


class RankAxisStep(Step):
    """Rank positions along one axis by a statistic."""

    name = "rank_axis"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        by = ctx.step_params.get("by")
        top_n = ctx.step_params.get("top_n")
        min_value = ctx.step_params.get("min_value")
        keep_ties = bool(ctx.step_params.get("keep_ties", False))
        descending = bool(ctx.step_params.get("descending", True))
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("rank_axis: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"rank_axis: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if by not in _STATS:
            raise StepError(
                f"rank_axis: 'by' must be one of {list(_STATS)}, "
                f"got {by!r}"
            )
        if top_n is None and min_value is None:
            raise StepError(
                "rank_axis: at least one of 'top_n' or 'min_value' "
                "is required"
            )
        if top_n is not None:
            top_n = int(top_n)
            if top_n < 1:
                raise StepError(
                    f"rank_axis: top_n must be >= 1, got {top_n}"
                )

        axis = form.dims.index(dim)
        moved = np.moveaxis(form.data, axis, 0).astype(np.float64)
        n_positions = moved.shape[0]
        flat = moved.reshape(n_positions, -1)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            valid = ~np.isnan(flat)
        else:
            valid = flat != missing_code

        stats = _compute_stat(by, flat, valid)

        finite_mask = np.isfinite(stats)
        if not finite_mask.any():
            raise StepError(
                f"rank_axis: no finite values for statistic "
                f"'{by}' along '{dim}'"
            )

        # Sort key: positions with non-finite stats go last.
        with np.errstate(invalid="ignore"):
            sort_keys = np.where(
                finite_mask,
                stats if descending else -stats,
                -np.inf if descending else np.inf,
            )
        order = np.argsort(-sort_keys, kind="stable")

        # Start with "everything passes" and intersect each criterion.
        selected_mask = np.ones(n_positions, dtype=bool)

        if min_value is not None:
            threshold = float(min_value)
            if descending:
                selected_mask &= finite_mask & (stats >= threshold)
            else:
                selected_mask &= finite_mask & (stats <= threshold)

        if top_n is not None:
            n_to_pick = min(top_n, int(finite_mask.sum()))
            ranked_mask = np.zeros(n_positions, dtype=bool)
            if n_to_pick > 0:
                ranked_positions = order[:n_to_pick]
                ranked_mask[ranked_positions] = True
                if keep_ties:
                    cutoff_key = sort_keys[ranked_positions[-1]]
                    tied = np.where(
                        finite_mask & (sort_keys == cutoff_key)
                    )[0]
                    ranked_mask[tied] = True
            selected_mask &= ranked_mask

        kept = np.where(selected_mask)[0]
        if kept.size == 0:
            raise StepError(
                f"rank_axis: no positions survived the selection "
                f"along '{dim}'."
            )

        # Preserve the original axis order.
        kept = np.sort(kept)

        new_form = form.subset_axis(dim, kept)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        kept_labels = [pos_to_label[int(i)] for i in kept]
        kept_set = set(kept.tolist())
        dropped_labels = [
            pos_to_label[i] for i in range(n_positions)
            if i not in kept_set
        ]
        stats_by_label = {
            pos_to_label[i]: (
                float(stats[i]) if np.isfinite(stats[i]) else None
            )
            for i in range(n_positions)
        }
        top_labels = [pos_to_label[int(i)] for i in order[:min(
            top_n if top_n is not None else n_positions, n_positions
        )]]

        self._export_data = {
            "dim": dim,
            "by": by,
            "descending": descending,
            "top_n": top_n,
            "min_value": min_value,
            "keep_ties": keep_ties,
            "n_before": int(n_positions),
            "n_after": int(kept.size),
            "n_removed": int(n_positions - kept.size),
            "kept_labels": kept_labels,
            "dropped_labels": dropped_labels,
            "stat_by_label": stats_by_label,
            "top_ranked_labels": top_labels,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "by": by,
            "n_before": int(n_positions),
            "n_after": int(kept.size),
        }

        print(
            f"[rank_axis] dim='{dim}' by='{by}' "
            f"{n_positions} -> {kept.size}"
            + (f" (top_n={top_n})" if top_n is not None else "")
            + (f" (min_value={min_value})" if min_value is not None else "")
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _compute_stat(name: str, flat: np.ndarray, valid: np.ndarray):
    masked = np.where(valid, flat, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with np.errstate(invalid="ignore", divide="ignore"):
            if name == "variance":
                return np.nanvar(masked, axis=1)
            if name == "std":
                return np.nanstd(masked, axis=1)
            if name == "mean":
                return np.nanmean(masked, axis=1)
            if name == "sum":
                return np.nansum(masked, axis=1)
            if name == "nonzero":
                nz = valid & (flat != 0)
                return nz.sum(axis=1).astype(np.float64)
            if name == "abs_mean":
                return np.nanmean(np.abs(masked), axis=1)
            if name == "max":
                return np.nanmax(masked, axis=1)
    raise StepError(f"rank_axis: no implementation for '{name}'")