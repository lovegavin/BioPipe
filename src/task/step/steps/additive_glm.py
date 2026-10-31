"""Additive generalized linear models with cubic B-spline bases."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = [
    "y",
    "linear_predictor",
    "fitted",
    "residual",
    "se_mean",
    "ci_low",
    "ci_high",
]


class AdditiveGlmStep(Step):
    """Fit an additive GLM with one cubic B-spline per predictor.

    Binomial and Poisson families are supported.  The basis uses
    :func:`patsy.bs`; for a given ``df`` it has the same quantile knots as
    R's ``splines::bs``.  This is an additive model, not a penalized GAM:
    no smoothing parameter is estimated and there are no interactions.
    """

    name = "additive_glm"
    title = "Additive B-spline GLM"
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
            "family": {
                "type": "string",
                "enum": ["binomial", "poisson"],
                "title": "分布族",
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
        "required": ["response_label", "predictors", "family"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        import patsy
        import statsmodels.api as sm

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        family_name = str(ctx.step_params["family"])
        raw_df = ctx.step_params.get("df", 4)
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if not 2 <= len(predictors) <= 8:
            raise StepError(
                f"{self.name}: need between 2 and 8 predictors"
            )
        if len(predictors) != len(set(predictors)):
            raise StepError(f"{self.name}: predictors must be unique")
        if response_label in predictors:
            raise StepError(
                f"{self.name}: response must not also be a predictor"
            )
        if family_name not in {"binomial", "poisson"}:
            raise StepError(
                f"{self.name}: family must be 'binomial' or 'poisson'"
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
        y_raw = numeric_column(frame, response_label, self.name)
        columns = [numeric_column(frame, name, self.name) for name in predictors]
        keep = np.isfinite(y_raw)
        for column in columns:
            keep &= np.isfinite(column)
        y_raw = np.asarray(y_raw[keep], dtype=np.float64)
        xs = [np.asarray(column[keep], dtype=np.float64) for column in columns]
        samples = (
            frame.loc[keep, "__sample__"].astype(str).to_numpy().tolist()
        )
        n = int(y_raw.size)
        if n < 8:
            raise StepError(f"{self.name}: need at least 8 complete rows")

        levels: list[float] | None = None
        if family_name == "binomial":
            levels_array = np.unique(y_raw)
            if levels_array.size != 2:
                raise StepError(
                    f"{self.name}: binomial response must have exactly two levels"
                )
            levels = [float(levels_array[0]), float(levels_array[1])]
            if np.array_equal(levels_array, np.array([0.0, 1.0])):
                y = y_raw
            else:
                y = (y_raw == levels_array[1]).astype(np.float64)
        else:
            if np.any(y_raw < 0):
                raise StepError(
                    f"{self.name}: poisson response must be nonnegative"
                )
            if not np.allclose(y_raw, np.rint(y_raw), rtol=0, atol=0):
                raise StepError(
                    f"{self.name}: poisson response must be integer counts"
                )
            y = np.rint(y_raw)

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
                f"{self.name}: additive GLM design is rank deficient"
            )

        family = (
            sm.families.Binomial()
            if family_name == "binomial"
            else sm.families.Poisson()
        )
        try:
            result = sm.GLM(y, design, family=family).fit(
                maxiter=100, disp=False
            )
            if not result.converged:
                raise StepError(f"{self.name}: GLM did not converge")
            fitted = np.asarray(result.fittedvalues, dtype=np.float64)
            linear = np.asarray(family.link(fitted), dtype=np.float64)
            prediction = result.get_prediction(design).summary_frame(
                alpha=1.0 - confidence
            )
        except StepError:
            raise
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: additive GLM fit failed: {exc}") from exc

        residual = y - fitted
        se_mean = np.asarray(prediction["mean_se"], dtype=np.float64)
        ci_low = np.asarray(prediction["mean_ci_lower"], dtype=np.float64)
        ci_high = np.asarray(prediction["mean_ci_upper"], dtype=np.float64)
        values = [y, linear, fitted, residual, se_mean, ci_low, ci_high]
        if not all(np.isfinite(value).all() for value in values):
            raise StepError(f"{self.name}: fitted values are not finite")

        null_deviance = float(result.null_deviance)
        deviance = float(result.deviance)
        pseudo_r2 = (
            1.0 - deviance / null_deviance
            if np.isfinite(null_deviance) and null_deviance > 0
            else float("nan")
        )
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
                "method": "additive_glm",
                "family": family_name,
                "link": str(family.link),
                "degree": 3,
                "terms": term_info,
                "confidence": confidence,
                "n": n,
                "n_basis": int(design.shape[1]),
                "deviance": deviance,
                "null_deviance": null_deviance,
                "pseudo_r2": float(pseudo_r2),
                "aic": float(result.aic),
                "converged": bool(result.converged),
            },
        )
        self._export = {
            "samples": samples,
            "y": y.tolist(),
            "linear_predictor": linear.tolist(),
            "fitted": fitted.tolist(),
            "residual": residual.tolist(),
            "se_mean": se_mean.tolist(),
            "ci_low": ci_low.tolist(),
            "ci_high": ci_high.tolist(),
            "terms": term_info,
            "coefficient_names": ["Intercept", *basis_names],
            "coefficients": np.asarray(result.params, dtype=np.float64).tolist(),
            "family": family_name,
            "levels": levels,
            "confidence": confidence,
            "n": n,
            "n_basis": int(design.shape[1]),
            "deviance": deviance,
            "null_deviance": null_deviance,
            "pseudo_r2": float(pseudo_r2),
            "aic": float(result.aic),
            "converged": bool(result.converged),
        }
        print(
            f"[{self.name}] n={n}, family={family_name}, "
            f"terms={len(predictors)}, deviance={deviance:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
