"""Vector autoregression with OLS estimation."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = ["coef", "se", "t", "p"]


class VarModelStep(Step):
    """Estimate a VAR(p) model with a deterministic OLS fit."""

    name = "var_model"
    title = "Vector autoregression"
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
            "lags": {"type": "integer", "minimum": 1, "default": 1},
            "trend": {
                "type": "string",
                "enum": ["c", "n", "ct"],
                "default": "c",
            },
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.tsa.api import VAR

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        lags = int(ctx.step_params.get("lags", 1))
        trend = ctx.step_params.get("trend", "c")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        features = [str(name) for name in frame.columns if name != "__sample__"]
        if len(features) < 2:
            raise StepError(f"{self.name}: need at least two series")
        if lags < 1:
            raise StepError(f"{self.name}: lags must be at least 1")

        data = np.column_stack(
            [numeric_column(frame, name, self.name) for name in features]
        )
        finite = np.isfinite(data).all(axis=1)
        data = data[finite]
        n = int(data.shape[0])
        if n <= lags * len(features) + 3:
            raise StepError(f"{self.name}: not enough complete observations")
        if np.any(np.var(data, axis=0) <= 0):
            raise StepError(f"{self.name}: every series needs positive variance")

        try:
            result = VAR(data).fit(lags, trend=trend)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: VAR fit failed: {exc}") from exc

        coefficients = np.asarray(result.params, dtype=np.float64)
        standard_errors = np.asarray(result.bse, dtype=np.float64)
        tvalues = np.asarray(result.tvalues, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        terms = [str(name) for name in result.model.exog_names]
        equations = [str(name) for name in result.model.endog_names]
        if coefficients.shape != (len(terms), len(equations)):
            raise StepError(f"{self.name}: unexpected VAR coefficient shape")
        if not (
            np.isfinite(coefficients).all()
            and np.isfinite(standard_errors).all()
            and np.isfinite(tvalues).all()
            and np.isfinite(pvalues).all()
        ):
            raise StepError(f"{self.name}: fitted coefficients are not finite")

        rows = []
        for equation_index in range(len(equations)):
            for term_index in range(len(terms)):
                rows.append(
                    [
                        coefficients[term_index, equation_index],
                        standard_errors[term_index, equation_index],
                        tvalues[term_index, equation_index],
                        pvalues[term_index, equation_index],
                    ]
                )
        block = np.asarray(rows, dtype=np.float64)
        ctx[out_name] = Form(
            data=block,
            dims=["equation", "term"],
            labels={
                "equation": {
                    name: index for index, name in enumerate(equations)
                },
                "term": {name: index for index, name in enumerate(terms)},
            },
            info={
                "method": "VAR",
                "lags": lags,
                "trend": trend,
                "nobs": int(result.nobs),
                "neqs": len(equations),
                "llf": float(result.llf),
                "aic": float(result.aic),
                "bic": float(result.bic),
                "hqic": float(result.hqic),
            },
        )
        self._export = {
            "equations": equations,
            "terms": terms,
            "coef": coefficients.tolist(),
            "se": standard_errors.tolist(),
            "t": tvalues.tolist(),
            "p": pvalues.tolist(),
            "llf": float(result.llf),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "hqic": float(result.hqic),
            "nobs": int(result.nobs),
        }
        print(
            f"[{self.name}] VAR({lags}) neqs={len(equations)}, "
            f"nobs={int(result.nobs)}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
