# src/task/step/steps/rename_dim.py
"""Rename one dimension of a form."""

from __future__ import annotations

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class RenameDimStep(Step):
    """Rename a single dimension.

    Params:
        from   : current dim name
        to     : new dim name
        output : context key for the result
    """

    name = "rename_dim"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        old = ctx.step_params["from"]
        new = ctx.step_params["to"]
        out_name = ctx.step_params.get("output", self.name)

        if old not in form.dims:
            raise StepError(
                f"rename_dim: dim '{old}' not present. "
                f"Available: {form.dims}"
            )
        if new in form.dims:
            raise StepError(
                f"rename_dim: target name '{new}' already exists. "
                f"Available: {form.dims}"
            )
        if not isinstance(new, str) or not new:
            raise StepError(
                f"rename_dim: 'to' must be a non-empty string, got {new!r}"
            )

        new_dims = [new if d == old else d for d in form.dims]

        new_labels = {k: dict(v) for k, v in form.labels.items()}
        new_labels[new] = new_labels.pop(old)

        ctx[out_name] = Form(
            data=form.data.copy(),
            dims=new_dims,
            labels=new_labels,
            info=dict(form.info),
        )

        self._export_data = {
            "from": old,
            "to": new,
            "input_dims": list(form.dims),
            "output_dims": new_dims,
        }

        print(f"[rename_dim] '{old}' -> '{new}' on {out_name}")

    def export(self, ctx: Context) -> dict:
        return self._export_data