"""Inverse-variance meta-regression of study-level effect sizes.

The input is one ``[study, feature]`` table containing an effect estimate,
its sampling variance, and one or more study-level moderators.  An
intercept and the requested moderators are fitted by weighted least
squares.  ``fixed`` uses inverse-variance weights; ``random`` adds a
DerSimonian-Laird between-study variance to each weight.
"""
from __future__ import annotations

import numpy as np
import statsmodels.api as sm
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, numeric_column, table_frame


_COLUMNS = ("coef", "se", "z", "P", "CI_low", "CI_high")


class MetaRegressionStep(Step):
    name = "meta_regression"
    title = "Meta-regression"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "scipy>=1.10", "statsmodels>=0.14"]
    dependency_imports = ["numpy", "scipy", "statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("study_dim", "study"), param("feature_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "study_dim": {"type": "string", "default": "study"},
            "feature_dim": {"type": "string", "default": "feature"},
            "effect_label": {"type": "string"},
            "variance_label": {"type": "string"},
            "moderators": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}, "default": []},
            "method": {"type": "string", "enum": ["fixed", "random"], "default": "random"},
            "confidence": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.95},
            "output": {"type": "string"},
        },
        "required": ["effect_label", "variance_label", "moderators"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        study_dim = ctx.step_params.get("study_dim", "study")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        effect_label = ctx.step_params["effect_label"]
        variance_label = ctx.step_params["variance_label"]
        moderators = list(ctx.step_params["moderators"])
        categorical = list(ctx.step_params.get("categorical", []))
        method = ctx.step_params.get("method", "random")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], study_dim, feature_dim, "meta_regression")
        effect = numeric_column(frame, effect_label, "meta_regression")
        variance = numeric_column(frame, variance_label, "meta_regression")
        design, terms = design_matrix(frame, moderators, categorical, "meta_regression")
        if len(frame) != design.shape[0]:
            raise StepError("meta_regression: design and data lengths differ")
        bad_variance = np.isfinite(variance) & (variance <= 0)
        if np.any(bad_variance):
            raise StepError("meta_regression: sampling variances must be positive")
        keep = (
            np.isfinite(effect)
            & np.isfinite(variance)
            & np.all(np.isfinite(design), axis=1)
        )
        effect = effect[keep]
        variance = variance[keep]
        design = design[keep]
        n, p = design.shape
        if n <= p + 1:
            raise StepError(
                f"meta_regression: need more than {p + 1} studies, got {n}"
            )
        if np.linalg.matrix_rank(design) < p:
            raise StepError("meta_regression: design matrix is rank deficient")

        weights = 1.0 / variance
        fit = sm.WLS(effect, design, weights=weights).fit()
        coef = np.asarray(fit.params, dtype=np.float64)
        qe = float(np.sum(weights * (effect - design @ coef) ** 2))
        df = n - p
        qep = float(stats.chi2.sf(qe, df))
        i2 = 100.0 * max(0.0, (qe - df) / qe) if qe > 0 else 0.0
        tau2 = 0.0
        if method == "random":
            # metafor's DL denominator is tr(P), not the single-intercept
            # simplification sum(w) - sum(w^2)/sum(w).
            xtwx_inv = np.linalg.inv(design.T @ (weights[:, None] * design))
            xtw2x = design.T @ ((weights ** 2)[:, None] * design)
            trace_p = float(np.sum(weights) - np.trace(xtwx_inv @ xtw2x))
            if trace_p > 0 and qe > df:
                tau2 = (qe - df) / trace_p
            if tau2 > 0:
                weights = 1.0 / (variance + tau2)
                fit = sm.WLS(effect, design, weights=weights).fit()
                coef = np.asarray(fit.params, dtype=np.float64)
        xtwx_inv = np.linalg.inv(design.T @ (weights[:, None] * design))
        se = np.sqrt(np.diag(xtwx_inv))
        z = coef / se
        pvals = 2.0 * stats.norm.sf(np.abs(z))
        crit = float(stats.norm.ppf(0.5 + confidence / 2.0))
        low = coef - crit * se
        high = coef + crit * se
        stats_matrix = np.column_stack([coef, se, z, pvals, low, high])
        form = Form(
            data=stats_matrix,
            dims=["term", "statistic"],
            labels={
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {name: i for i, name in enumerate(_COLUMNS)},
            },
            info={
                "missing_code": np.nan,
                "method": method,
                "moderators": moderators,
                "n_studies": n,
                "n_parameters": p,
                "tau2": float(tau2),
                "Q": qe,
                "Q_p": qep,
                "I2": float(i2),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "method": method,
            "terms": terms,
            "coef": coef.tolist(),
            "se": se.tolist(),
            "z": z.tolist(),
            "p": pvals.tolist(),
            "ci_low": low.tolist(),
            "ci_high": high.tolist(),
            "n_studies": n,
            "n_parameters": p,
            "tau2": float(tau2),
            "Q": qe,
            "Q_p": qep,
            "I2": float(i2),
        }
        print(
            f"[meta_regression] {method}: n={n}, p={p}, tau2={tau2:.6g}, I2={i2:.2f}%"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
