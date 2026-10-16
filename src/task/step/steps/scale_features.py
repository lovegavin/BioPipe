"""Z-score standardisation along one axis of a 2D numeric Form.

Input: any 2D Form. Missing cells are recognised from
info["missing_code"]; when that code is NaN, non-finite cells count
as missing. Missing cells stay missing in the output.

For every position along the *other* axis, values are rescaled so
that, across ``dim``, they have mean 0 and population standard
deviation 1:

    x' = (x - mean_over_dim) / std_over_dim

Mean and std are computed with NaN-aware aggregation. Positions whose
std is effectively zero are shifted to 0 (the numerator is already
0 for a constant row), not turned into NaN.

When ``max_value`` is given, the rescaled value is clipped to
[-max_value, +max_value] after standardisation.

Output: same dims and labels as the input. ``data`` is replaced;
``representation`` becomes ``"scaled"``; genotype/alphabet semantics
and encoders are cleared because the numeric values no longer mean
what they meant.

Params:
    dim        : axis to standardise *along* (default "sample")
                 e.g. dim="sample" scales each feature across samples
                 dim="feature" scales each sample across features
    max_value  : optional clip on the absolute standardised value
    output     : context key (default: step name)
"""
from __future__ import annotations

import numbers
import warnings

import numpy as np

from src.core import Form, StepError
from src.core.contracts import MISSING, param, port
from src.core.forms.metadata import project_metadata
from src.task.context import Context
from src.task.step.base import Step


def _missing_mask(data, code):
    if isinstance(code, numbers.Real) and not isinstance(code, bool) and np.isnan(code):
        return ~np.isfinite(data)
    return data == code


class ScaleFeaturesStep(Step):
    """Z-score standardise a 2D Form along one axis."""

    name = "scale_features"
    category = "data"
    icon = "SlidersHorizontal"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "dim": {"type": "string", "default": "sample", "minLength": 1},
            "max_value": {
                "type": ["number", "null"],
                "default": None,
            },
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("dim")],
        info={"missing_code": MISSING},
    )]
    output_contract = {"mode": "transform", "representation": "scaled"}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim", "sample")
        max_value = ctx.step_params.get("max_value")
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2:
            raise StepError(
                f"scale_features: expected a 2D Form, got ndim={form.data.ndim}"
            )
        if dim not in form.dims:
            raise StepError(
                f"scale_features: dim '{dim}' not in {form.dims}"
            )
        if max_value is not None:
            if not isinstance(max_value, (int, float)) or isinstance(max_value, bool):
                raise StepError(
                    f"scale_features: max_value must be a number, "
                    f"got {max_value!r}"
                )
            if max_value <= 0:
                raise StepError(
                    f"scale_features: max_value must be > 0, got {max_value}"
                )

        data = form.data.astype(np.float64)
        missing = _missing_mask(data, form.info.get("missing_code", np.nan))
        masked = np.where(missing, np.nan, data)

        axis = form.dims.index(dim)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            mean = np.nanmean(masked, axis=axis, keepdims=True)
            std = np.nanstd(masked, axis=axis, keepdims=True)

        # Constant-along-dim rows have std 0; produce 0 (not NaN).
        std_safe = np.where(std < 1e-12, 1.0, std)
        scaled = (masked - mean) / std_safe

        if max_value is not None:
            scaled = np.clip(scaled, -float(max_value), float(max_value))

        scaled[missing] = np.nan

        info, axis_info = project_metadata(form, derived=True)
        info["missing_code"] = np.nan
        info["representation"] = "scaled"

        out_form = Form(
            data=scaled.astype(np.float32),
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=info,
            axis_info=axis_info,
        )
        ctx[out_name] = out_form

        self._export_data = {
            "dim": dim,
            "max_value": max_value,
            "shape": list(form.data.shape),
            "n_missing_in": int(missing.sum()),
            "n_values_clipped": (
                int(np.sum(np.abs(scaled) >= float(max_value) - 1e-9))
                if max_value is not None else 0
            ),
        }

        print(
            f"[scale_features] along '{dim}', shape="
            f"{form.data.shape}, max_value={max_value}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
