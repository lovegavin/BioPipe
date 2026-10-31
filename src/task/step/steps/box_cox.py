"""Box-Cox power transformation with optional per-feature MLE.

The transformation is ``(x^lambda - 1) / lambda`` for ``lambda != 0`` and
``log(x)`` for ``lambda == 0``.  Each feature can have its own lambda,
estimated by maximising the profile likelihood (the same criterion used by
R's ``MASS::boxcox``).

Missing cells are preserved.  ``shift`` can be used to make a feature
strictly positive before fitting; the shift is applied before the transform
and recorded in ``info``.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


def _ordered(labels: dict) -> list[str]:
    return [name for name, _ in sorted(labels.items(), key=lambda item: item[1])]


def _boxcox(values: np.ndarray, lam: float) -> np.ndarray:
    if abs(lam) < 1e-12:
        return np.log(values)
    return (np.power(values, lam) - 1.0) / lam


class BoxCoxStep(Step):
    """Box-Cox transform each feature, optionally estimating lambda."""

    name = "box_cox"
    title = "Box-Cox transform"
    category = "Data"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.24", "scipy>=1.10"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
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
            "lambdas": {
                "oneOf": [
                    {"type": "number"},
                    {
                        "type": "object",
                        "additionalProperties": {"type": "number"},
                    },
                ],
                "title": "固定 lambda（标量或按特征映射；省略则逐特征 MLE）",
            },
            "shift": {
                "type": "number",
                "minimum": 0.0,
                "default": 0.0,
                "title": "变换前加常数，使取值严格为正",
            },
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        shift = float(ctx.step_params.get("shift", 0.0))

        if sample_dim not in form.dims or feature_dim not in form.dims:
            raise StepError(
                f"{self.name}: dims must include {sample_dim!r} and {feature_dim!r}, "
                f"got {form.dims}"
            )
        if sample_dim == feature_dim:
            raise StepError(f"{self.name}: sample_dim and feature_dim must differ")
        if shift < 0.0:
            raise StepError(f"{self.name}: shift must be >= 0, got {shift}")

        axis = form.dims.index(sample_dim)
        values = np.moveaxis(np.asarray(form.data), axis, 0).astype(np.float64)
        samples = _ordered(form.labels[sample_dim])
        features = _ordered(form.labels[feature_dim])
        if values.shape != (len(samples), len(features)):
            raise StepError(
                f"{self.name}: data shape {values.shape} does not match "
                f"{len(samples)} samples x {len(features)} features"
            )

        explicit = self._parse_lambdas(ctx.step_params.get("lambdas"), features)
        transformed = np.full(values.shape, np.nan, dtype=np.float64)
        lambdas: dict[str, float] = {}
        n_valid: dict[str, int] = {}

        for j, feature in enumerate(features):
            column = values[:, j]
            keep = np.isfinite(column)
            if not np.any(keep):
                lambdas[feature] = float("nan")
                n_valid[feature] = 0
                continue
            work = column[keep] + shift
            if np.any(work <= 0.0):
                raise StepError(
                    f"{self.name}: feature {feature!r} must be strictly positive "
                    f"after shift; use shift > 0"
                )
            if work.size < 3:
                raise StepError(
                    f"{self.name}: feature {feature!r} needs at least three "
                    f"finite values, got {work.size}"
                )
            lam = explicit.get(feature)
            if lam is None:
                try:
                    lam = float(stats.boxcox_normmax(work, method="mle"))
                except Exception as exc:
                    raise StepError(
                        f"{self.name}: lambda estimation failed for {feature!r}: {exc}"
                    ) from exc
            if not np.isfinite(lam):
                raise StepError(
                    f"{self.name}: lambda for {feature!r} is not finite"
                )
            transformed[keep, j] = _boxcox(work, float(lam))
            lambdas[feature] = float(lam)
            n_valid[feature] = int(work.size)

        data = np.moveaxis(transformed, 0, axis).astype(np.float32)
        info, axis_info = project_metadata(form, derived=True)
        info.update(
            missing_code=np.nan,
            representation="box_cox",
            shift=shift,
            lambdas={key: value for key, value in lambdas.items()},
            n_valid=n_valid,
        )
        ctx[out_name] = Form(
            data=data,
            dims=list(form.dims),
            labels={name: dict(labels) for name, labels in form.labels.items()},
            info=info,
            axis_info=axis_info,
        )

        finite = data[np.isfinite(data)]
        self._export = {
            "shift": shift,
            "lambdas": lambdas,
            "n_valid": n_valid,
            "n_features": len(features),
            "n_samples": len(samples),
            "transformed_min": float(finite.min()) if finite.size else None,
            "transformed_max": float(finite.max()) if finite.size else None,
        }
        print(
            f"[{self.name}] shift={shift:g} features={len(features)} "
            f"lambdas={lambdas}"
        )

    def _parse_lambdas(self, raw, features: list[str]) -> dict[str, float]:
        if raw is None:
            return {}
        if isinstance(raw, bool):
            raise StepError(f"{self.name}: lambdas must be a number or mapping")
        if isinstance(raw, (int, float)):
            value = float(raw)
            if not np.isfinite(value):
                raise StepError(f"{self.name}: lambda must be finite")
            return {feature: value for feature in features}
        if isinstance(raw, dict):
            unknown = sorted(set(raw) - set(features))
            if unknown:
                raise StepError(
                    f"{self.name}: unknown feature(s) in lambdas: {unknown}"
                )
            out: dict[str, float] = {}
            for key, value in raw.items():
                if isinstance(value, bool):
                    raise StepError(f"{self.name}: lambda for {key!r} must be numeric")
                try:
                    number = float(value)
                except (TypeError, ValueError) as exc:
                    raise StepError(
                        f"{self.name}: lambda for {key!r} must be numeric"
                    ) from exc
                if not np.isfinite(number):
                    raise StepError(f"{self.name}: lambda for {key!r} must be finite")
                out[str(key)] = number
            return out
        raise StepError(f"{self.name}: lambdas must be a number or mapping")

    def export(self, ctx: Context) -> dict:
        return self._export
