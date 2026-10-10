# src/task/step/steps/describe.py
"""Describe step: print and export a summary of an input form."""

from __future__ import annotations

import numpy as np

from src.task.context import Context
from src.task.step.base import Step


class DescribeStep(Step):
    """Print a summary of one input form.

    Params: none.
    """

    name = "describe"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]

        data = form.data
        finite = data[np.isfinite(data)]

        summary = {
            "shape": list(data.shape),
            "dims": list(form.dims),
            "info": _serialize_info(form.info),
            "labels": {
                dim: {str(k): int(v) for k, v in mapping.items()}
                for dim, mapping in form.labels.items()
            },
            "global": {
                "min": float(np.min(finite)) if finite.size else None,
                "max": float(np.max(finite)) if finite.size else None,
                "mean": float(np.mean(finite)) if finite.size else None,
                "std": float(np.std(finite)) if finite.size else None,
                "n_valid": int(finite.size),
                "n_missing": int(data.size - finite.size),
            },
        }
        self._export_data = summary

        print("[describe] form")
        print(f"  shape:  {tuple(data.shape)}")
        print(f"  dims:   {form.dims}")
        print(f"  info:   {form.info}")
        if form.labels:
            print(f"  labels: {form.labels}")
        if finite.size > 0:
            print(
                f"  global: min={float(np.min(finite)):.4f} "
                f"max={float(np.max(finite)):.4f} "
                f"mean={float(np.mean(finite)):.4f} "
                f"std={float(np.std(finite)):.4f} "
                f"n_valid={finite.size} "
                f"n_missing={data.size - finite.size}"
            )
        else:
            print("  global: all cells missing")

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _serialize_info(info: dict) -> dict:
    out: dict = {}
    for k, v in info.items():
        if k == "encoders":
            out[k] = {
                dim: {
                    label: {
                        "name": enc.name,
                        "mapping": {
                            str(kk): int(vv)
                            for kk, vv in enc.mapping.items()
                        },
                    }
                    for label, enc in cols.items()
                }
                for dim, cols in v.items()
            }
        elif isinstance(v, (int, float, str, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple)):
            out[k] = list(v)
        elif isinstance(v, dict):
            out[k] = v
        else:
            out[k] = str(v)
    return out