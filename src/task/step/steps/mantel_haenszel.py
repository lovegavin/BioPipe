"""Mantel-Haenszel stratified odds ratio and association test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class MantelHaenszelStep(Step):
    name = "mantel_haenszel"
    title = "Mantel-Haenszel test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("stratum_dim", "stratum"), param("feature_dim", "feature")])
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "stratum_dim": {"type": "string", "default": "stratum"},
            "feature_dim": {"type": "string", "default": "feature"},
            "case_exposed": {"type": "string", "default": "case_exposed"},
            "case_unexposed": {"type": "string", "default": "case_unexposed"},
            "control_exposed": {"type": "string", "default": "control_exposed"},
            "control_unexposed": {"type": "string", "default": "control_unexposed"},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        stratum_dim = ctx.step_params.get("stratum_dim", "stratum")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        names = [
            ctx.step_params.get("case_exposed", "case_exposed"),
            ctx.step_params.get("case_unexposed", "case_unexposed"),
            ctx.step_params.get("control_exposed", "control_exposed"),
            ctx.step_params.get("control_unexposed", "control_unexposed"),
        ]
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        if form.data.ndim != 2:
            raise StepError("mantel_haenszel: input must be 2D")
        for dim in (stratum_dim, feature_dim):
            if dim not in form.dims:
                raise StepError(f"mantel_haenszel: dim {dim!r} not in {form.dims}")
        if not (0 < confidence < 1):
            raise StepError("mantel_haenszel: confidence must be in (0, 1)")

        labels = form.labels.get(feature_dim, {})
        missing = [name for name in names if name not in labels]
        if missing:
            raise StepError(f"mantel_haenszel: columns not found: {missing}")
        data = np.asarray(form.data, dtype=np.float64)
        if form.dims.index(stratum_dim) == 1:
            data = data.T
        cols = [data[:, labels[name]] for name in names]
        keep = np.ones(data.shape[0], dtype=bool)
        for col in cols:
            keep &= np.isfinite(col)
        cols = [col[keep] for col in cols]
        if np.any(np.asarray(cols) < 0):
            raise StepError("mantel_haenszel: cell counts must be non-negative")
        if not np.allclose(np.asarray(cols), np.round(np.asarray(cols))):
            raise StepError("mantel_haenszel: cell counts must be integers")
        a, b, c, d = (col.astype(np.int64) for col in cols)
        n = a + b + c + d
        valid = n > 1
        a, b, c, d, n = a[valid], b[valid], c[valid], d[valid], n[valid]
        if n.size == 0:
            raise StepError("mantel_haenszel: no stratum has a positive table size > 1")

        r1 = a + b
        r2 = c + d
        c1 = a + c
        c2 = b + d
        expected = r1 * c1 / n
        variance = r1 * r2 * c1 * c2 / (n * n * (n - 1))
        sum_var = float(variance.sum())
        if sum_var <= 0:
            raise StepError("mantel_haenszel: zero variance; table has no information")
        delta = float(a.sum() - expected.sum())
        statistic = delta * delta / sum_var
        p = float(stats.chi2.sf(statistic, 1))

        odds_num = float(np.sum(a * d / n))
        odds_den = float(np.sum(b * c / n))
        if odds_den == 0:
            odds_ratio = float("inf") if odds_num > 0 else float("nan")
            ci_low = ci_high = float("nan")
        else:
            odds_ratio = odds_num / odds_den
            # Robins-Breslow-Greenland variance of log(OR_MH).
            p_r = (a + d) / n
            q_s = (b + c) / n
            r = a * d / n
            s = b * c / n
            sr = float(r.sum())
            ss = float(s.sum())
            if sr == 0 or ss == 0:
                ci_low = 0.0 if sr == 0 else float("nan")
                ci_high = float("inf") if ss == 0 else float("nan")
            else:
                var_log = (
                    float(np.sum(p_r * r)) / (2.0 * sr * sr)
                    + float(np.sum(p_r * s + q_s * r)) / (2.0 * sr * ss)
                    + float(np.sum(q_s * s)) / (2.0 * ss * ss)
                )
                if var_log < 0:
                    var_log = 0.0
                z = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))
                log_or = np.log(odds_ratio)
                ci_low = float(np.exp(log_or - z * np.sqrt(var_log)))
                ci_high = float(np.exp(log_or + z * np.sqrt(var_log)))

        values = [
            ("mh_statistic", statistic),
            ("p", p),
            ("odds_ratio", odds_ratio),
            ("ci_low", ci_low),
            ("ci_high", ci_high),
            ("n_strata", float(n.size)),
            ("n_total", float(n.sum())),
        ]
        out = make_form(
            [[value] for _, value in values],
            ["statistic", "value"],
            {"statistic": {name: i for i, (name, _) in enumerate(values)},
             "value": {"value": 0}},
        )
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "mh_statistic": statistic, "p": p, "odds_ratio": odds_ratio,
            "ci_low": ci_low, "ci_high": ci_high,
            "n_strata": int(n.size), "n_total": int(n.sum()),
            "confidence": confidence,
        }
        print(
            f"[mantel_haenszel] strata={n.size} OR={odds_ratio:.4g} "
            f"chi2={statistic:.4g} p={p:.4g}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
