"""Gaussian-process regression with a fixed RBF kernel."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class GaussianProcessRegressorStep(Step):
    """Fit a Gaussian-process regressor with a fixed RBF kernel.

    The kernel length scale and noise level are fixed by the user; no
    marginal-likelihood optimisation is performed.  This keeps fits
    deterministic and makes the posterior mean/variance reproducible from
    the closed-form GP equations.
    """

    name = "gaussian_process_regressor"
    title = "Gaussian-process regression"
    category = "Machine Learning"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "pandas>=2.0", "scikit-learn>=1.3"]
    dependency_imports = ["numpy", "pandas", "sklearn"]
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
            "response_label": {"type": "string", "title": "响应列"},
            "predictors": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "title": "预测变量列",
            },
            "length_scale": {
                "oneOf": [
                    {"type": "number", "exclusiveMinimum": 0},
                    {
                        "type": "object",
                        "additionalProperties": {
                            "type": "number",
                            "exclusiveMinimum": 0,
                        },
                    },
                ],
                "default": 1.0,
                "title": "RBF 长度尺度",
            },
            "alpha": {
                "type": "number",
                "minimum": 0,
                "default": 1e-6,
                "title": "观测噪声方差",
            },
            "normalize_y": {
                "type": "boolean",
                "default": True,
                "title": "标准化响应",
            },
            "output": {"type": "string"},
        },
        "required": ["response_label", "predictors"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RBF

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        alpha = float(ctx.step_params.get("alpha", 1e-6))
        normalize_y = bool(ctx.step_params.get("normalize_y", True))
        out_name = ctx.step_params.get("output", self.name)

        if not predictors:
            raise StepError(f"{self.name}: predictors must not be empty")
        if len(set(predictors)) != len(predictors):
            raise StepError(f"{self.name}: predictors must be unique")
        if response_label in predictors:
            raise StepError(f"{self.name}: response must not be a predictor")
        if alpha < 0:
            raise StepError(f"{self.name}: alpha must be nonnegative")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        missing = [name for name in [response_label, *predictors] if name not in frame.columns]
        if missing:
            raise StepError(f"{self.name}: missing columns: {missing}")

        columns = [numeric_column(frame, name, self.name) for name in [response_label, *predictors]]
        matrix = np.column_stack(columns)
        keep = np.isfinite(matrix).all(axis=1)
        matrix = matrix[keep]
        samples = frame.loc[keep, "__sample__"].astype(str).to_numpy().tolist()
        n = int(matrix.shape[0])
        if n < 2:
            raise StepError(f"{self.name}: need at least 2 complete observations")

        y = np.asarray(matrix[:, 0], dtype=np.float64)
        x = np.asarray(matrix[:, 1:], dtype=np.float64)
        raw_scale = ctx.step_params.get("length_scale", 1.0)
        if isinstance(raw_scale, dict):
            unknown = sorted(set(raw_scale) - set(predictors))
            if unknown:
                raise StepError(f"{self.name}: unknown length_scale keys: {unknown}")
            length_scale = np.asarray(
                [float(raw_scale.get(name, 1.0)) for name in predictors],
                dtype=np.float64,
            )
        else:
            length_scale = np.full(x.shape[1], float(raw_scale), dtype=np.float64)
        if np.any(~np.isfinite(length_scale)) or np.any(length_scale <= 0):
            raise StepError(f"{self.name}: length_scale must be positive")

        try:
            model = GaussianProcessRegressor(
                kernel=RBF(length_scale=length_scale, length_scale_bounds="fixed"),
                alpha=alpha,
                optimizer=None,
                normalize_y=normalize_y,
                random_state=0,
            )
            model.fit(x, y)
            fitted, std = model.predict(x, return_std=True)
        except (ValueError, np.linalg.LinAlgError) as exc:
            raise StepError(f"{self.name}: Gaussian-process fit failed: {exc}") from exc

        fitted = np.asarray(fitted, dtype=np.float64)
        std = np.asarray(std, dtype=np.float64)
        if (
            fitted.shape != (n,)
            or std.shape != (n,)
            or not np.isfinite(fitted).all()
            or not np.isfinite(std).all()
        ):
            raise StepError(f"{self.name}: non-finite Gaussian-process prediction")
        residual = y - fitted
        r2 = float("nan")
        if np.ptp(y) > 0:
            r2 = float(1.0 - np.sum(residual**2) / np.sum((y - y.mean()) ** 2))
        rmse = float(np.sqrt(np.mean(residual**2)))

        rows = np.column_stack([y, fitted, residual, std])
        form = Form(
            rows,
            ["sample", "statistic"],
            {
                "sample": {name: i for i, name in enumerate(samples)},
                "statistic": {
                    "observed": 0,
                    "fitted": 1,
                    "residual": 2,
                    "se": 3,
                },
            },
            {
                "method": "gaussian_process",
                "kernel": "RBF",
                "length_scale": length_scale.tolist(),
                "alpha": alpha,
                "normalize_y": normalize_y,
                "n": n,
                "n_features": int(x.shape[1]),
                "r2": r2,
                "rmse": rmse,
                "log_marginal_likelihood": float(model.log_marginal_likelihood_value_),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export = {
            "samples": samples,
            "observed": y.tolist(),
            "fitted": fitted.tolist(),
            "residual": residual.tolist(),
            "se": std.tolist(),
            "length_scale": length_scale.tolist(),
            "alpha": alpha,
            "normalize_y": normalize_y,
            "n": n,
            "n_features": int(x.shape[1]),
            "r2": r2,
            "rmse": rmse,
            "log_marginal_likelihood": float(model.log_marginal_likelihood_value_),
        }
        print(
            f"[{self.name}] n={n}, features={x.shape[1]}, "
            f"rmse={rmse:.4f}, r2={r2:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
