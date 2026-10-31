"""ARIMA time-series model."""
from __future__ import annotations

import warnings

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = ["coef", "se", "z", "P", "CI_low", "CI_high"]


class ArimaStep(Step):
    """Fit a non-seasonal ARIMA(p, d, q) model by maximum likelihood."""

    name = "arima"
    title = "ARIMA model"
    category = "Statistics"
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
            "value_label": {"type": "string"},
            "p": {"type": "integer", "minimum": 0, "maximum": 4, "default": 1},
            "d": {"type": "integer", "minimum": 0, "maximum": 2, "default": 0},
            "q": {"type": "integer", "minimum": 0, "maximum": 4, "default": 0},
            "trend": {"type": "string", "enum": ["c", "n"], "default": "c"},
            "confidence": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 1,
                "default": 0.95,
            },
            "maxiter": {"type": "integer", "minimum": 10, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from scipy.stats import norm
        from statsmodels.tsa.arima.model import ARIMA

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        p = int(ctx.step_params.get("p", 1))
        d = int(ctx.step_params.get("d", 0))
        q = int(ctx.step_params.get("q", 0))
        trend = ctx.step_params.get("trend", "c")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        maxiter = int(ctx.step_params.get("maxiter", 200))
        out_name = ctx.step_params.get("output", self.name)

        if p + q == 0:
            raise StepError(f"{self.name}: p + q must be at least 1")
        if trend == "c" and d > 0:
            raise StepError(
                f"{self.name}: a constant trend is not supported with d > 0; "
                "use trend='n'"
            )
        if not (0 < confidence < 1):
            raise StepError(f"{self.name}: confidence must be in (0, 1)")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = np.asarray(values, dtype=np.float64)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < max(20, p + q + d + 5):
            raise StepError(
                f"{self.name}: need more finite observations for this order"
            )
        if float(np.var(values)) <= 0:
            raise StepError(f"{self.name}: series has zero variance")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(
                    values,
                    order=(p, d, q),
                    trend=trend,
                    enforce_stationarity=True,
                    enforce_invertibility=True,
                )
                result = model.fit(
                    cov_type="approx", method_kwargs={"maxiter": maxiter}
                )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: ARIMA fit failed: {exc}") from exc

        names = [str(name) for name in result.param_names]
        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        if not (np.isfinite(params).all() and np.isfinite(bse).all()):
            raise StepError(f"{self.name}: fitted parameters are not finite")
        if np.any(bse <= 0):
            raise StepError(f"{self.name}: fitted standard errors are not positive")

        try:
            sigma_index = names.index("sigma2")
        except ValueError as exc:
            raise StepError(f"{self.name}: fitted model has no sigma2") from exc

        keep = [i for i, name in enumerate(names) if name != "sigma2"]
        terms = [names[i] for i in keep]
        coefs = params[keep]
        standard_errors = bse[keep]
        zvalues = coefs / standard_errors
        pvalues = 2.0 * norm.sf(np.abs(zvalues))
        alpha = 1.0 - confidence
        interval = np.asarray(result.conf_int(alpha=alpha), dtype=np.float64)
        if interval.shape != (len(names), 2):
            raise StepError(f"{self.name}: unexpected confidence interval shape")
        ci = interval[keep]

        table = np.column_stack(
            [coefs, standard_errors, zvalues, pvalues, ci[:, 0], ci[:, 1]]
        )
        ctx[out_name] = Form(
            data=table,
            dims=["term", "statistic"],
            labels={
                "term": {name: index for index, name in enumerate(terms)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "model": "ARIMA",
                "order": [p, d, q],
                "trend": trend,
                "n": n,
                "sigma2": float(params[sigma_index]),
                "sigma2_se": float(bse[sigma_index]),
                "loglikelihood": float(result.llf),
                "aic": float(result.aic),
                "bic": float(result.bic),
            },
        )
        self._export = {
            "terms": terms,
            "coef": [float(value) for value in coefs],
            "se": [float(value) for value in standard_errors],
            "z": [float(value) for value in zvalues],
            "p": [float(value) for value in pvalues],
            "ci_low": [float(value) for value in ci[:, 0]],
            "ci_high": [float(value) for value in ci[:, 1]],
            "sigma2": float(params[sigma_index]),
            "sigma2_se": float(bse[sigma_index]),
            "loglikelihood": float(result.llf),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "order": [p, d, q],
            "n": n,
        }
        print(
            f"[{self.name}] ARIMA({p},{d},{q}) n={n}, "
            f"aic={float(result.aic):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
