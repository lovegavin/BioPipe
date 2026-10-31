"""Additive regression with cubic B-spline bases."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = [
    "y",
    "fitted",
    "residual",
    "se_mean",
    "ci_low",
    "ci_high",
]


class AdditiveSplineRegressionStep(Step):
    """Fit an additive OLS model with one cubic B-spline per predictor.

    The basis uses :func:`patsy.bs`; for a given ``df`` it has the same
    quantile knots as R's ``splines::bs``.  This is an additive model,
    not a penalized GAM: no smoothing parameter is estimated.
    """

    name = "additive_spline_regression"
    title = "Additive B-spline regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = [
        "numpy>=1.24",
        "pandas>=2.0",
        "patsy>=0.5",
        "statsmodels>=0.14",
    ]
    dependency_imports = ["numpy", "pandas", "patsy", "statsmodels"]
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
            "response_label": {"type": "string", "title": "因变量列"},
            "predictors": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 8,
                "uniqueItems": True,
                "title": "自变量列",
            },
            "df": {
                "oneOf": [
                    {
                        "type": "integer",
                        "minimum": 4,
                        "maximum": 10,
                        "default": 4,
                    },
                    {
                        "type": "object",
                        "additionalProperties": {
                            "type": "integer",
                            "minimum": 4,
                            "maximum": 10,
                        },
                    },
                ],
                "title": "B-spline 自由度",
            },
            "confidence": {
                "type": "number",
                "exclusiveMinimum": 0,
                "exclusiveMaximum": 1,
                "default": 0.95,
                "title": "置信水平",
            },
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        import patsy
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        raw_df = ctx.step_params.get("df", 4)
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if len(predictors) != len(set(predictors)):
            raise StepError(f"{self.name}: predictors must be unique")
        if response_label in predictors:
            raise StepError(
                f"{self.name}: response must not also be a predictor"
            )
        if not 0.0 < confidence < 1.0:
            raise StepError(f"{self.name}: confidence must be in (0, 1)")

        if isinstance(raw_df, dict):
            unknown = sorted(set(raw_df) - set(predictors))
            if unknown:
                raise StepError(
                    f"{self.name}: df keys not predictors: {unknown}"
                )
            df_map = {name: int(raw_df.get(name, 4)) for name in predictors}
        else:
            value = int(raw_df)
            df_map = {name: value for name in predictors}
        for name, df in df_map.items():
            if not 4 <= df <= 10:
                raise StepError(
                    f"{self.name}: df for {name!r} must be in 4..10"
                )

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        y = numeric_column(frame, response_label, self.name)
        columns = [numeric_column(frame, name, self.name) for name in predictors]
        keep = np.isfinite(y)
        for column in columns:
            keep &= np.isfinite(column)
        y = np.asarray(y[keep], dtype=np.float64)
        xs = [np.asarray(column[keep], dtype=np.float64) for column in columns]
        samples = (
            frame.loc[keep, "__sample__"].astype(str).to_numpy().tolist()
        )
        n = int(y.size)
        if n < 8:
            raise StepError(f"{self.name}: need at least 8 complete rows")

        blocks = []
        term_info = []
        basis_names = []
        for name, x, df in zip(predictors, xs, [df_map[p] for p in predictors]):
            if np.ptp(x) <= 0:
                raise StepError(
                    f"{self.name}: predictor {name!r} must vary"
                )
            try:
                basis = patsy.bs(
                    x, df=df, degree=3, include_intercept=False
                )
            except (ValueError, TypeError) as exc:
                raise StepError(
                    f"{self.name}: could not build basis for {name!r}: {exc}"
                ) from exc
            basis = np.asarray(basis, dtype=np.float64)
            if basis.ndim != 2 or basis.shape[1] < 1:
                raise StepError(
                    f"{self.name}: basis for {name!r} is empty"
                )
            blocks.append(basis)
            basis_names.extend(
                [f"{name}[{index}]" for index in range(basis.shape[1])]
            )
            term_info.append(
                {
                    "predictor": name,
                    "df": int(df),
                    "n_basis": int(basis.shape[1]),
                }
            )

        design = sm.add_constant(np.column_stack(blocks), has_constant="add")
        if design.shape[1] < 2:
            raise StepError(f"{self.name}: design matrix is empty")
        if n < design.shape[1] + 2:
            raise StepError(
                f"{self.name}: need at least n_basis + 2 complete rows"
            )
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError(
                f"{self.name}: additive spline design is rank deficient"
            )

        try:
            result = sm.OLS(y, design).fit()
            prediction = result.get_prediction(design).summary_frame(
                alpha=1.0 - confidence
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(
                f"{self.name}: additive spline fit failed: {exc}"
            ) from exc

        fitted = np.asarray(result.fittedvalues, dtype=np.float64)
        residual = np.asarray(result.resid, dtype=np.float64)
        se_mean = np.asarray(prediction["mean_se"], dtype=np.float64)
        ci_low = np.asarray(prediction["mean_ci_lower"], dtype=np.float64)
        ci_high = np.asarray(prediction["mean_ci_upper"], dtype=np.float64)
        values = [y, fitted, residual, se_mean, ci_low, ci_high]
        if not all(np.isfinite(value).all() for value in values):
            raise StepError(f"{self.name}: fitted values are not finite")

        ctx[out_name] = Form(
            data=np.column_stack(values).astype(np.float64),
            dims=["sample", "statistic"],
            labels={
                "sample": {name: index for index, name in enumerate(samples)},
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "method": "additive_cubic_bspline",
                "degree": 3,
                "terms": term_info,
                "confidence": confidence,
                "n": n,
                "r2": float(result.rsquared),
                "adj_r2": float(result.rsquared_adj),
                "aic": float(result.aic),
                "bic": float(result.bic),
                "n_basis": int(design.shape[1]),
            },
        )
        self._export = {
            "samples": samples,
            "y": y.tolist(),
            "fitted": fitted.tolist(),
            "residual": residual.tolist(),
            "se_mean": se_mean.tolist(),
            "ci_low": ci_low.tolist(),
            "ci_high": ci_high.tolist(),
            "terms": term_info,
            "coefficient_names": ["Intercept", *basis_names],
            "coefficients": np.asarray(result.params, dtype=np.float64).tolist(),
            "confidence": confidence,
            "n": n,
            "r2": float(result.rsquared),
            "adj_r2": float(result.rsquared_adj),
            "aic": float(result.aic),
            "bic": float(result.bic),
            "n_basis": int(design.shape[1]),
        }
        print(
            f"[{self.name}] n={n}, terms={len(predictors)}, "
            f"r2={float(result.rsquared):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
