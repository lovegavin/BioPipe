"""Probit regression for a binary response."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import design_matrix, table_frame

_STATISTICS = ["coef", "se", "z", "P", "CI_low", "CI_high"]


class ProbitRegressionStep(Step):
    """Fit a binomial probit regression by maximum likelihood."""

    name = "probit_regression"
    title = "Probit regression"
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
            "response_label": {"type": "string"},
            "predictors": {
                "type": "array", "items": {"type": "string"}, "minItems": 1,
            },
            "categorical": {"type": "array", "items": {"type": "string"}},
            "maxiter": {"type": "integer", "minimum": 20, "default": 200},
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.api import GLM, families

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        maxiter = int(ctx.step_params.get("maxiter", 200))
        out_name = ctx.step_params.get("output", self.name)

        if response_label in predictors:
            raise StepError(
                f"{self.name}: response {response_label!r} cannot also be a predictor"
            )
        missing = [name for name in categorical if name not in predictors]
        if missing:
            raise StepError(
                f"{self.name}: categorical names not in predictors: {missing}"
            )

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        if response_label not in frame.columns:
            raise StepError(
                f"{self.name}: response {response_label!r} not found"
            )
        for name in predictors:
            if name not in frame.columns:
                raise StepError(f"{self.name}: predictor {name!r} not found")

        valid = frame[response_label].notna()
        for name in predictors:
            if name in categorical:
                valid &= frame[name].notna()
            else:
                valid &= np.isfinite(
                    pd.to_numeric(frame[name], errors="coerce")
                )
        frame = frame.loc[valid].reset_index(drop=True)
        if len(frame) < 8:
            raise StepError(f"{self.name}: fewer than eight complete rows")

        raw = frame[response_label]
        numeric = pd.to_numeric(raw, errors="coerce")
        if not numeric.notna().all():
            raise StepError(f"{self.name}: response must be numeric")
        values = np.asarray(numeric, dtype=np.float64)
        distinct = sorted(set(values.tolist()))
        if len(distinct) != 2:
            raise StepError(
                f"{self.name}: response must have exactly two levels"
            )
        if distinct == [0.0, 1.0]:
            y = values.astype(np.int64)
            levels = ["0", "1"]
        else:
            low, high = distinct
            y = (values == high).astype(np.int64)
            levels = [str(low), str(high)]

        x, names = design_matrix(frame, predictors, categorical, self.name)
        if x.shape[1] == 0:
            raise StepError(f"{self.name}: no predictor columns remain")
        try:
            result = GLM(
                y,
                x,
                family=families.Binomial(link=families.links.Probit()),
            ).fit(maxiter=maxiter, disp=False)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: probit fit failed: {exc}") from exc

        params = np.asarray(result.params, dtype=np.float64)
        bse = np.asarray(result.bse, dtype=np.float64)
        pvalues = np.asarray(result.pvalues, dtype=np.float64)
        conf = np.asarray(result.conf_int(), dtype=np.float64)
        if not (np.isfinite(params).all() and np.isfinite(bse).all()):
            raise StepError(f"{self.name}: fitted parameters are not finite")
        if np.any(bse <= 0):
            raise StepError(f"{self.name}: fitted standard errors are not positive")
        zvalues = params / bse
        llf = float(result.llf)
        pbar = float(y.mean())
        if 0.0 < pbar < 1.0:
            null_ll = float(
                len(y)
                * (
                    pbar * np.log(pbar)
                    + (1.0 - pbar) * np.log(1.0 - pbar)
                )
            )
            pseudo_r2 = 1.0 - llf / null_ll
        else:
            pseudo_r2 = float("nan")
        table = np.column_stack(
            [params, bse, zvalues, pvalues, conf[:, 0], conf[:, 1]]
        )
        ctx[out_name] = Form(
            data=table,
            dims=["term", "statistic"],
            labels={
                "term": {name: index for index, name in enumerate(names)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "link": "probit",
                "n": int(len(y)),
                "n_events": int(y.sum()),
                "levels": levels,
                "loglikelihood": llf,
                "aic": float(result.aic),
                "pseudo_r2": pseudo_r2,
            },
        )
        self._export = {
            "terms": list(names),
            "coef": [float(value) for value in params],
            "se": [float(value) for value in bse],
            "z": [float(value) for value in zvalues],
            "p": [float(value) for value in pvalues],
            "ci_low": [float(value) for value in conf[:, 0]],
            "ci_high": [float(value) for value in conf[:, 1]],
            "n": int(len(y)),
            "n_events": int(y.sum()),
            "levels": levels,
            "loglikelihood": llf,
            "aic": float(result.aic),
            "pseudo_r2": pseudo_r2,
        }
        print(
            f"[{self.name}] n={len(y)}, events={int(y.sum())}, "
            f"terms={len(names)}, aic={float(result.aic):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
