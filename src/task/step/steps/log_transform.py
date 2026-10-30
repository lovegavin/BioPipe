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
from src.core.forms.metadata import project_metadata


class LogTransformStep(Step):
    """Apply log_base(x + pseudocount) elementwise."""
    provider = 'biopipe-expression'
    parameters_file = 'log_transform.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'log_transform',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Log',
     'description': '按指定底数与伪计数变换',
     'category': '数据整理',
     'icon': 'Function',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [],
                               'labels': [],
                               'parallel': []}],
                   'output': {'mode': 'transform', 'representation': 'log_transform'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



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

        info, axis_info = project_metadata(form, derived=True)
        info.update(missing_code=np.nan, representation="log_transform")
        ctx[out_name] = Form(
            data=transformed,
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=info,
            axis_info=axis_info,
        )

        finite = transformed[np.isfinite(transformed)]
        finite_after = transformed[np.isfinite(transformed)]
        finite_before = data[np.isfinite(data)]

        def _stats(arr):
            if arr.size == 0:
                return {
                    "min": None, "max": None,
                    "mean": None, "std": None,
                    "q25": None, "q50": None, "q75": None,
                }
            return {
                "min": float(arr.min()),
                "max": float(arr.max()),
                "mean": float(arr.mean()),
                "std": float(arr.std()),
                "q25": float(np.quantile(arr, 0.25)),
                "q50": float(np.quantile(arr, 0.50)),
                "q75": float(np.quantile(arr, 0.75)),
            }

        self._export_data = {
            "base": base_value,
            "base_input": base,
            "pseudocount": pseudocount,
            "formula": f"log_{base_value:g}(x + {pseudocount:g})",
            "n_valid": int(finite_after.size),
            "n_missing": int(transformed.size - finite_after.size),
            "before": _stats(finite_before),
            "after": _stats(finite_after),
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