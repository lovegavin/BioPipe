"""Ordinal logistic regression with a proportional-odds model."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats21_common import design_matrix, table_frame


class OrdinalLogisticStep(Step):
    """Proportional-odds ordinal regression via statsmodels OrderedModel."""

    name = "ordinal_logistic"
    title = "Ordinal logistic regression"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("feature_dim", "feature")],
        )
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "response_label": {"type": "string"},
            "predictors": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "categorical": {"type": "array", "items": {"type": "string"}},
            "distr": {"type": "string", "enum": ["logit", "probit"], "default": "logit"},
            "maxiter": {"type": "integer", "minimum": 20, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.miscmodels.ordinal_model import OrderedModel

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        frame = table_frame(form, sample_dim, feature_dim, "ordinal_logistic")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        missing = [name for name in categorical if name not in predictors]
        if missing:
            raise StepError(
                f"ordinal_logistic: categorical names not in predictors: {missing}"
            )
        if response_label not in frame.columns:
            raise StepError(
                f"ordinal_logistic: response {response_label!r} not found"
            )
        for name in predictors:
            if name not in frame.columns:
                raise StepError(
                    f"ordinal_logistic: predictor {name!r} not found"
                )

        valid = frame[response_label].notna()
        for name in predictors:
            if name in categorical:
                valid &= frame[name].notna()
            else:
                valid &= np.isfinite(
                    __import__("pandas").to_numeric(frame[name], errors="coerce")
                )
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 5:
            raise StepError("ordinal_logistic: fewer than five complete rows")

        raw = [str(value) for value in frame[response_label].tolist()]
        levels = sorted(set(raw))
        if len(levels) < 2:
            raise StepError("ordinal_logistic: response needs at least two levels")
        mapping = {value: i for i, value in enumerate(levels)}
        y = np.asarray([mapping[value] for value in raw], dtype=np.int64)
        x_full, names_full = design_matrix(
            frame, predictors, categorical, "ordinal_logistic"
        )
        # OrderedModel supplies the cut points itself and rejects a constant
        # column in exog, so drop the intercept produced by design_matrix.
        if names_full and names_full[0] == "Intercept":
            x = x_full[:, 1:]
            names = names_full[1:]
        else:
            x = x_full
            names = names_full
        if x.shape[1] == 0:
            raise StepError("ordinal_logistic: no predictor columns remain")

        distr_name = ctx.step_params.get("distr", "logit")
        maxiter = int(ctx.step_params.get("maxiter", 200))
        try:
            result = OrderedModel(y, x, distr=distr_name).fit(
                method="bfgs", maxiter=maxiter, disp=False
            )
        except Exception as exc:  # statsmodels raises several optimizer errors
            raise StepError(f"ordinal_logistic: fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        n_terms = x.shape[1]
        n_thresholds = len(params) - n_terms
        if n_thresholds < 1:
            raise StepError("ordinal_logistic: unexpected parameter vector length")

        # OrderedModel stores the first cut point directly and later cut
        # points as exponentiated increments; report the actual thresholds.
        thresholds = np.asarray(
            result.model.transform_threshold_params(params)[1:-1], dtype=np.float64
        )
        raw_thresholds = params[-n_thresholds:]
        cov = np.asarray(result.cov_params(), dtype=np.float64)
        gamma_cov = cov[-n_thresholds:, -n_thresholds:]
        jac = np.zeros((n_thresholds, n_thresholds), dtype=np.float64)
        jac[:, 0] = 1.0
        for j in range(1, n_thresholds):
            jac[j, 1 : j + 1] = np.exp(raw_thresholds[1 : j + 1])
        threshold_se = np.sqrt(np.maximum(np.diag(jac @ gamma_cov @ jac.T), 0.0))

        terms = names + [f"threshold_{i + 1}" for i in range(n_thresholds)]
        rows = []
        for i in range(n_terms):
            se = bse[i]
            z = params[i] / se if np.isfinite(se) and se > 0 else np.nan
            rows.append(
                [
                    params[i],
                    se,
                    z,
                    pvalues[i],
                    conf[i, 0],
                    conf[i, 1],
                ]
            )
        zcrit = float(stats.norm.ppf(0.975))
        for i in range(n_thresholds):
            value = thresholds[i]
            se = threshold_se[i]
            z = value / se if np.isfinite(se) and se > 0 else np.nan
            p = float(2.0 * stats.norm.sf(abs(z))) if np.isfinite(z) else np.nan
            rows.append(
                [
                    value,
                    se,
                    z,
                    p,
                    value - zcrit * se,
                    value + zcrit * se,
                ]
            )
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=["term", "statistic"],
            labels={
                "term": {name: i for i, name in enumerate(terms)},
                "statistic": {
                    "coef": 0,
                    "se": 1,
                    "z": 2,
                    "P": 3,
                    "CI_low": 4,
                    "CI_high": 5,
                },
            },
            info={
                "missing_code": np.nan,
                "levels": levels,
                "n": int(len(y)),
                "distr": distr_name,
                "loglike": float(result.llf),
                "aic": float(result.aic),
                "thresholds": [float(value) for value in thresholds],
            },
        )
        self._export_data = {
            "n": int(len(y)),
            "n_levels": len(levels),
            "levels": levels,
            "distr": distr_name,
            "aic": float(result.aic),
            "loglike": float(result.llf),
            "terms": terms,
            "thresholds": [float(value) for value in thresholds],
        }
        print(
            f"[ordinal_logistic] n={len(y)}, levels={len(levels)}, "
            f"terms={len(terms)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
