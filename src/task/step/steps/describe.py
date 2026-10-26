# src/task/step/steps/describe.py
"""Describe step: print and export a summary of an input form."""

from __future__ import annotations

import numpy as np

from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import MISSING, param, port


class DescribeStep(Step):
    """Print a summary of one input form.

    Params: none.
    """
    parameters_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
     'type': 'object',
     'properties': {},
     'additionalProperties': True,
     'required': []}
    title = '数据概览'
    category = '数据整理'
    icon = 'ListBullets'
    description = '查看形状、标签、缺失情况与全局统计。支持分块读取。'

    name = "describe"
    inputs_arity = 1
    outputs = []
    input_contracts = [port()]
    output_contract = {"mode": "report"}

    supports_streaming = True
    stream_protocol = "flat-reduction-v1"

    def run_stream(self, ctx: Context, stream: dict) -> None:
        """Bounded finite-cell statistics; float64 moments may differ by rounding."""
        count, mean, m2 = 0, 0.0, 0.0
        minimum = maximum = None
        for block in stream["chunks"]:
            finite = block[np.isfinite(block)]
            if finite.size:
                values = finite.astype(np.float64, copy=False)
                n = int(values.size)
                local_mean = float(values.mean())
                local_m2 = float(values.var()) * n
                delta = local_mean - mean
                total = count + n
                m2 += local_m2 + delta * delta * count * n / total
                mean += delta * n / total
                count = total
                low, high = float(values.min()), float(values.max())
                minimum = low if minimum is None else min(minimum, low)
                maximum = high if maximum is None else max(maximum, high)
                del values
            del finite
        meta = stream["metadata"]
        self._export_data = {
            "shape": list(stream["shape"]), "dims": list(meta["dims"]),
            "info": _serialize_info(meta["info"]),
            "axis_info": meta.get("axis_info", {}),
            "labels": {dim: {str(k): int(v) for k, v in labels.items()}
                       for dim, labels in meta["labels"].items()},
            "global": {"min": minimum, "max": maximum,
                       "mean": mean if count else None,
                       "std": float(np.sqrt(max(0.0, m2 / count))) if count else None,
                       "n_valid": count,
                       "n_missing": int(np.prod(stream["shape"])) - count},
        }
        print(f"[describe] streamed shape={stream['shape']}, n_valid={count}")

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]

        data = form.data
        finite = data[np.isfinite(data)]

        summary = {
            "shape": list(data.shape),
            "dims": list(form.dims),
            "info": _serialize_info(form.info),
            "axis_info": form.axis_info,
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
        # if form.labels:
        #     print(f"  labels: {form.labels}")
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
    def value(item):
        if isinstance(item, np.generic):
            return value(item.item())
        if isinstance(item, np.ndarray):
            return value(item.tolist())
        if isinstance(item, (list, tuple)):
            return [value(v) for v in item]
        if isinstance(item, dict):
            return {str(k): value(v) for k, v in item.items()}
        if isinstance(item, float) and not np.isfinite(item):
            return str(item)
        if isinstance(item, (str, int, float, bool)) or item is None:
            return item
        return str(item)
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
        else:
            out[k] = value(v)
    return out
