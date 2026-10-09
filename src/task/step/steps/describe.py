# src/task/step/steps/describe.py
"""Describe step: print an overview of an input form."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step


class DescribeStep(Step):
    """Print a summary of one input form."""

    name = "describe"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]

        print("[describe] form")
        print(f"  shape:  {form.data.shape}")
        print(f"  dims:   {form.dims}")
        print(f"  info:   {form.info}")
        # if form.labels:
        #     print(f"  labels: {form.labels}")

        if form.data.size > 0:
            print(
                f"  global: min={float(np.min(form.data)):.4f} "
                f"max={float(np.max(form.data)):.4f} "
                f"mean={float(np.mean(form.data)):.4f} "
                f"std={float(np.std(form.data)):.4f}"
            )
        else:
            print("  global: empty")