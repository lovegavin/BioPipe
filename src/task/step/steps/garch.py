"""GARCH volatility model."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = ["coef", "se", "t", "p"]


class GarchStep(Step):
    """Fit a GARCH(p, q) model with a constant or zero mean."""

    name = "garch"
    title = "GARCH volatility model"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["arch>=6"]
    dependency_imports = ["arch"]
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
            "mean": {
                "type": "string",
                "enum": ["Constant", "Zero"],
                "default": "Constant",
            },
            "p": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
            "q": {"type": "integer", "minimum": 1, "maximum": 3, "default": 1},
            "dist": {"type": "string", "enum": ["normal", "t"], "default": "normal"},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from arch import arch_model

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        mean = ctx.step_params.get("mean", "Constant")
        p = int(ctx.step_params.get("p", 1))
        q = int(ctx.step_params.get("q", 1))
        dist = ctx.step_params.get("dist", "normal")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 50:
            raise StepError(f"{self.name}: need at least 50 finite observations")
        if float(np.var(values)) <= 0:
            raise StepError(f"{self.name}: series has zero variance")
        if p < 1 or q < 1:
            raise StepError(f"{self.name}: p and q must be at least 1")

        try:
            model = arch_model(
                values,
                mean=mean,
                vol="GARCH",
                p=p,
                q=q,
                dist=dist,
                rescale=False,
            )
            result = model.fit(disp="off", show_warning=False)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: GARCH fit failed: {exc}") from exc
        if int(result.convergence_flag) != 0:
            raise StepError(
                f"{self.name}: GARCH fit did not converge "
                f"(flag {result.convergence_flag})"
            )

        names = [str(name) for name in result.params.index]
        coefficients = np.asarray(result.params, dtype=np.float64)
        standard_errors = np.asarray(result.std_err, dtype=np.float64)
        tvalues = np.asarray(result.tvalues, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        if (
            not np.isfinite(coefficients).all()
            or not np.isfinite(standard_errors).all()
            or not np.isfinite(tvalues).all()
            or not np.isfinite(pvalues).all()
        ):
            raise StepError(f"{self.name}: fitted parameters are not finite")
        if np.any(standard_errors <= 0):
            raise StepError(f"{self.name}: fitted standard errors are not positive")

        alpha_beta = 0.0
        for name, value in zip(names, coefficients):
            if name.startswith("alpha[") or name.startswith("beta["):
                alpha_beta += float(value)
        table = np.column_stack(
            [coefficients, standard_errors, tvalues, pvalues]
        )
        ctx[out_name] = Form(
            data=table,
            dims=["parameter", "statistic"],
            labels={
                "parameter": {name: index for index, name in enumerate(names)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "method": "GARCH",
                "mean": mean,
                "p": p,
                "q": q,
                "dist": dist,
                "nobs": int(result.nobs),
                "persistence": float(alpha_beta),
                "loglikelihood": float(result.loglikelihood),
                "aic": float(result.aic),
                "bic": float(result.bic),
            },
        )
        self._export = {
            "parameters": names,
            "coef": [float(value) for value in coefficients],
            "se": [float(value) for value in standard_errors],
            "t": [float(value) for value in tvalues],
            "p": [float(value) for value in pvalues],
            "persistence": float(alpha_beta),
            "conditional_volatility": [
                float(value) for value in np.asarray(result.conditional_volatility)
            ],
            "residuals": [float(value) for value in np.asarray(result.resid)],
            "std_residuals": [float(value) for value in np.asarray(result.std_resid)],
            "loglikelihood": float(result.loglikelihood),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "nobs": int(result.nobs),
        }
        print(
            f"[{self.name}] GARCH({p},{q}) n={int(result.nobs)}, "
            f"persistence={alpha_beta:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
