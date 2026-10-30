"""Cochran-Armitage trend test for ordered groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class CochranArmitageStep(Step):
    name = "cochran_armitage"
    title = "Cochran-Armitage trend test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("group_dim", "group"), param("feature_dim", "feature")])
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "group_dim": {"type": "string", "default": "group"},
            "feature_dim": {"type": "string", "default": "feature"},
            "cases_column": {"type": "string", "default": "cases"},
            "total_column": {"type": "string", "default": "total"},
            "group_scores": {"type": "array", "items": {"type": "number"}},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        group_dim = ctx.step_params.get("group_dim", "group")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        cases_name = ctx.step_params.get("cases_column", "cases")
        total_name = ctx.step_params.get("total_column", "total")
        scores_arg = ctx.step_params.get("group_scores")
        out_name = ctx.step_params.get("output", self.name)
        if form.data.ndim != 2:
            raise StepError("cochran_armitage: input must be 2D")
        for dim in (group_dim, feature_dim):
            if dim not in form.dims:
                raise StepError(f"cochran_armitage: dim {dim!r} not in {form.dims}")
        labels = form.labels.get(feature_dim, {})
        for name in (cases_name, total_name):
            if name not in labels:
                raise StepError(f"cochran_armitage: column {name!r} not found")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(group_dim) == 1:
            data = data.T
        cases = data[:, labels[cases_name]]
        totals = data[:, labels[total_name]]
        keep = np.isfinite(cases) & np.isfinite(totals)
        cases, totals = cases[keep], totals[keep]
        if cases.size < 2:
            raise StepError("cochran_armitage: need at least two groups")
        if np.any(totals <= 0):
            raise StepError("cochran_armitage: totals must be positive")
        if np.any(cases < 0) or np.any(cases > totals):
            raise StepError("cochran_armitage: cases must satisfy 0 <= cases <= total")
        if not np.allclose(cases, np.round(cases)) or not np.allclose(totals, np.round(totals)):
            raise StepError("cochran_armitage: cases and totals must be integers")
        cases = cases.astype(np.float64)
        totals = totals.astype(np.float64)
        scores = np.arange(totals.size, dtype=np.float64) if scores_arg is None else np.asarray(scores_arg, dtype=np.float64)
        if scores.size != totals.size:
            raise StepError("cochran_armitage: group_scores length must equal the number of groups")
        if not np.isfinite(scores).all():
            raise StepError("cochran_armitage: group_scores must be finite")
        n_total = float(totals.sum())
        p_bar = float(cases.sum()) / n_total
        if not (0.0 < p_bar < 1.0):
            raise StepError("cochran_armitage: all groups have the same outcome proportion 0 or 1")
        weighted_score = float(np.sum(totals * scores) / n_total)
        sxx = float(np.sum(totals * (scores - weighted_score) ** 2))
        if sxx <= 0:
            raise StepError("cochran_armitage: group scores have zero weighted variance")
        p = cases / totals
        sxy = float(np.sum(totals * (scores - weighted_score) * (p - p_bar)))
        statistic = sxy * sxy / (p_bar * (1.0 - p_bar) * sxx)
        pvalue = float(stats.chi2.sf(statistic, 1))
        slope = sxy / sxx
        z = float(np.sign(slope) * np.sqrt(statistic)) if slope != 0 else 0.0
        values = [
            ("statistic", statistic), ("p", pvalue), ("z", z),
            ("slope", slope), ("n_total", n_total), ("n_groups", float(totals.size)),
        ]
        out = make_form(
            [[value] for _, value in values],
            ["statistic", "value"],
            {"statistic": {name: i for i, (name, _) in enumerate(values)},
             "value": {"value": 0}},
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "p": pvalue, "z": z, "slope": slope,
            "n_total": int(n_total), "n_groups": int(totals.size),
        }
        print(f"[cochran_armitage] groups={totals.size} chi2={statistic:.4g} p={pvalue:.4g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
