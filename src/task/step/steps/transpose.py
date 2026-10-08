# src/task/step/steps/transpose.py
"""Transpose step: reorder the axes of a form.

The step permutes axes. Labels are unchanged: a label names a position
along a given dimension, and dimensions are reordered, not relabeled.
A label that was at position 3 of ``field`` is still at position 3 of
``field`` after the transpose; only ``field``'s axis index changes.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class TransposeStep(Step):
    """Reorder the axes of a form.

    Params:

    * ``order``  — list of dimension names, the desired new axis order.
      Must be a permutation of the form's current dims.
    * ``output`` — context key for the result.
    """

    name = "transpose"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        order = ctx.step_params["order"]
        out_name = ctx.step_params["output"]

        if not isinstance(order, list) or not order:
            raise StepError("transpose: 'order' must be a non-empty list")

        if len(order) != len(set(order)):
            raise StepError(
                f"transpose: 'order' contains duplicates: {order}"
            )

        if set(order) != set(form.dims):
            raise StepError(
                f"transpose: 'order' {order} must be a permutation of "
                f"dims {form.dims}"
            )

        # numpy.transpose: axes[i] = old axis index that becomes new axis i.
        axes = [form.dims.index(name) for name in order]
        new_data = np.transpose(form.data, axes=axes).copy()

        # Labels do not change. Positions are per-dim, not per-axis.
        new_labels = {k: dict(v) for k, v in form.labels.items()}

        ctx[out_name] = Form(
            data=new_data.astype(np.float32),
            dims=list(order),
            labels=new_labels,
            info=dict(form.info),
        )

        print(
            f"[transpose] {form.dims} -> {list(order)}, "
            f"shape {form.data.shape} -> {new_data.shape}"
        )