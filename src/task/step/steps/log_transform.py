# src/task/step/steps/log_transform.py
"""Log-transform a Form.

Applies log_base(x + pseudocount) elementwise. Standard third step
after normalization, for any count-based matrix (RNA-seq,
single-cell, metagenomics, proteomics).

Missing values are preserved: any cell that is missing on input
stays missing on output. ``dims``, ``labels``, ``info`` and
``axis_info`` are passed through unchanged.

Params:
    base        : log base, either 2, 10, "e" (default 2)
    pseudocount : value added before the log (default 1)
    output      : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class LogTransformStep(Step):
    """Apply log_base(x + pseudocount) elementwise."""

    name = "log_transform"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        base = ctx.step_params.get("base", 2)
        pseudocount = float(ctx.step_params.get("pseudocount", 1))
        out_name = ctx.step_params.get("output", self.name)

        base_value = _resolve_base(base)
        if pseudocount <= 0:
            raise StepError(
                f"log_transform: pseudocount must be > 0, "
                f"got {pseudocount}"
            )

        data = form.data.astype(np.float64)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(data)
        else:
            missing = data == missing_code

        shifted = data + pseudocount
        with np.errstate(invalid="ignore", divide="ignore"):
            transformed = np.log(shifted) / np.log(base_value)

        transformed = np.where(missing, np.nan, transformed)
        transformed = transformed.astype(np.float32)

        ctx[out_name] = Form(
            data=transformed,
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=dict(form.info),
            axis_info={k: list(v) for k, v in form.axis_info.items()},
        )

        finite = transformed[np.isfinite(transformed)]

        self._export_data = {
            "base": base_value,
            "base_input": base,
            "pseudocount": pseudocount,
            "n_valid": int(finite.size),
            "n_missing": int(transformed.size - finite.size),
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "mean": float(finite.mean()) if finite.size else None,
            "std": float(finite.std()) if finite.size else None,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "base": base_value,
            "pseudocount": pseudocount,
            "n_valid": int(finite.size),
            "n_missing": int(transformed.size - finite.size),
        }

        if finite.size:
            print(
                f"[log_transform] base={base_value:g} "
                f"pseudocount={pseudocount:g} "
                f"range [{finite.min():.3f}, {finite.max():.3f}]"
            )
        else:
            print(
                f"[log_transform] base={base_value:g} "
                f"pseudocount={pseudocount:g} (all cells missing)"
            )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _resolve_base(base) -> float:
    if isinstance(base, str):
        if base == "e":
            return float(np.e)
        if base in ("2", "10"):
            return float(base)
        raise StepError(
            f"log_transform: base string must be 'e', '2' or '10', "
            f"got {base!r}"
        )
    try:
        base_f = float(base)
    except (TypeError, ValueError) as exc:
        raise StepError(
            f"log_transform: base must be a number or 'e', got {base!r}"
        ) from exc
    if base_f <= 0 or base_f == 1:
        raise StepError(
            f"log_transform: base must be > 0 and != 1, got {base_f}"
        )
    return base_f