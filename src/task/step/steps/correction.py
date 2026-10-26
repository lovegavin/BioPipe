# src/task/step/steps/correction.py
"""Multiple-testing correction."""

from __future__ import annotations

import numpy as np
import statsmodels.api as sm

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.forms.metadata import project_metadata


class CorrectionStep(Step):
    """Multiple-testing correction on a result table.

    Params:
        method : "bonferroni" or "fdr"
        alpha  : significance level (default 0.05)
        pfield : name of the p-value column (default "P")
        dim    : dimension carrying the statistic labels (default
                 "statistic")
        output : context key for the result
    """
    provider = 'biopipe-genetics'
    parameters_file = 'correction.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'correction',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'FDR',
     'description': '进行 Bonferroni 或 FDR 校正。',
     'category': '统计分析',
     'icon': 'CheckSquare',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': 'statistic'}],
                               'labels': [{'dim': {'param': 'dim', 'default': 'statistic'},
                                           'values': {'param': 'pfield', 'default': 'P'}}],
                               'parallel': [],
                               'ndim': 2,
                               'values': 'pvalue'}],
                   'output': {'mode': 'correction'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'title_aliases': ['多重检验校正'],
     'title_parameter': {'key': 'method', 'values': {'fdr': 'FDR', 'bonferroni': 'Bonferroni'}}}




    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        method = ctx.step_params.get("method", "bonferroni")
        alpha = float(ctx.step_params.get("alpha", 0.05))
        pfield = ctx.step_params.get("pfield", "P")
        dim = ctx.step_params.get("dim", "statistic")
        out_name = ctx.step_params.get("output", self.name)

        if method not in ("bonferroni", "fdr"):
            raise StepError(
                f"correction: method must be 'bonferroni' or 'fdr', "
                f"got {method!r}"
            )
        if not 0.0 < alpha < 1.0:
            raise StepError(
                f"correction: alpha must be in (0, 1), got {alpha}"
            )
        if dim not in form.dims:
            raise StepError(
                f"correction: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if dim not in form.labels:
            raise StepError(
                f"correction: dim '{dim}' has no labels."
            )
        if pfield not in form.labels[dim]:
            raise StepError(
                f"correction: '{pfield}' not in dim '{dim}'. "
                f"Available: {sorted(form.labels[dim])}"
            )

        stat_axis = form.dims.index(dim)
        p_pos = form.labels[dim][pfield]

        pvals = np.take(form.data, p_pos, axis=stat_axis).astype(float)

        finite = np.isfinite(pvals)
        n_tests = int(finite.sum())

        if n_tests == 0:
            raise StepError(
                "correction: no finite p-values in the input form."
            )

        qvals = np.full(pvals.shape, np.nan, dtype=float)

        if method == "bonferroni":
            corrected = np.minimum(pvals * n_tests, 1.0)
            qvals[finite] = corrected[finite]
        else:
            _, q_adj, _, _ = sm.stats.multipletests(
                pvals[finite], alpha=alpha, method="fdr_bh"
            )
            qvals[finite] = q_adj

        significant = finite & (qvals < alpha)

        new_data = np.concatenate(
            [
                form.data,
                qvals.reshape(_shape_with_singleton(form, stat_axis, -1)),
                significant.astype(np.float32).reshape(
                    _shape_with_singleton(form, stat_axis, -1)
                ),
            ],
            axis=stat_axis,
        ).astype(np.float32)

        if {"Q_VALUE", "SIGNIFICANT"} & form.labels[dim].keys():
            raise StepError("correction: Q_VALUE or SIGNIFICANT already exists")
        existing = form.labels[dim]
        next_pos = max(existing.values()) + 1
        new_dim_labels = dict(existing)
        new_dim_labels["Q_VALUE"] = next_pos
        new_dim_labels["SIGNIFICANT"] = next_pos + 1

        new_labels = {k: dict(v) for k, v in form.labels.items()}
        new_labels[dim] = new_dim_labels

        new_info, new_axis_info = project_metadata(form)
        for field in new_axis_info.get(dim, []):
            new_info[field] = list(new_info[field]) + [None, None]
        new_info["correction_method"] = method
        ctx[out_name] = Form(
            data=new_data,
            dims=list(form.dims),
            labels=new_labels,
            info=new_info,
            axis_info=new_axis_info,
        )

        n_sig = int(significant.sum())

        # --- Export --------------------------------------------------
        # The per-row data lives along the *other* axis (the feature /
        # variant axis). Its labels come from that axis, not from the
        # statistic axis.
        other_axis = 1 - stat_axis
        other_dim = form.dims[other_axis]
        other_labels = form.labels[other_dim]
        pos_to_label = {v: k for k, v in other_labels.items()}

        per_row = []
        for pos in range(pvals.shape[0]):
            lab = pos_to_label.get(pos, f"#{pos}")
            p = float(pvals[pos]) if np.isfinite(pvals[pos]) else None
            q = float(qvals[pos]) if np.isfinite(qvals[pos]) else None
            per_row.append({
                "label": lab,
                "p": p,
                "q": q,
                "significant": bool(significant[pos]),
            })

        self._export_data = {
            "method": method,
            "alpha": alpha,
            "n_tests": n_tests,
            "n_significant": n_sig,
            "min_q": float(np.nanmin(qvals)) if n_tests else None,
            "results": per_row,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "alpha": alpha,
            "n_tests": n_tests,
            "n_significant": n_sig,
            "min_q": float(np.nanmin(qvals)) if n_tests else None,
        }

        print(
            f"[correction] method='{method}' n_tests={n_tests} "
            f"n_significant={n_sig} (alpha={alpha})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _shape_with_singleton(form: Form, axis: int, size: int):
    shape = list(form.data.shape)
    shape[axis] = size
    return tuple(shape)