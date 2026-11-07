"""Sliding-window GC content and GC/AT skew profiles.

GC skew ``(G - C) / (G + C)`` and AT skew ``(A - T) / (A + T)`` are the classic
signals for replication origin/terminus and strand bias in bacterial genomes.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_STATISTICS = ("gc_content", "gc_skew", "at_skew", "n_gc")


def skew_windows(sequence: str, window: int, step: int) -> list[tuple[int, int, float, float, float, int]]:
    text = sequence.upper()
    length = len(text)
    rows: list[tuple[int, int, float, float, float, int]] = []
    if length < window:
        return rows
    for start in range(0, length - window + 1, step):
        chunk = text[start : start + window]
        counts = {base: chunk.count(base) for base in "ACGT"}
        gc = counts["G"] + counts["C"]
        at = counts["A"] + counts["T"]
        gc_content = gc / window
        gc_skew = (counts["G"] - counts["C"]) / gc if gc else 0.0
        at_skew = (counts["A"] - counts["T"]) / at if at else 0.0
        rows.append((start, start + window, gc_content, gc_skew, at_skew, gc))
    return rows


class SequenceGcSkewProfileStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_gc_skew_profile.SequenceGcSkewProfileStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_gc_skew_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GC skew profile",
        "description": "Sliding-window GC content and GC/AT skew profile of nucleotide sequences.",
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("sequence_gc_skew_profile: a sequence form input is required")
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        window_dim = str(params.get("window_dim") or "window")
        out_name = str(params.get("output") or "windows")
        window = params.get("window")
        window = 50 if window is None else window
        step = params.get("step")
        step = 10 if step is None else step

        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "sequence_gc_skew_profile: sequence input expected "
                f"[{sequence_dim}, {position_dim}], got {list(form.dims)}"
            )
        if isinstance(window, bool) or not isinstance(window, int) or not 2 <= window <= 100000:
            raise StepError("sequence_gc_skew_profile: window must be an integer between 2 and 100000")
        if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= window:
            raise StepError("sequence_gc_skew_profile: step must be a positive integer not above the window")

        sequences = decode_sequences(form, sequence_dim, position_dim)
        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        starts: list[int] = []
        ends: list[int] = []
        sequence_indexes: list[int] = []
        for index, sequence in enumerate(sequences):
            for start, end, gc_content, gc_skew, at_skew, n_gc in skew_windows(sequence, int(window), int(step)):
                label = f"seq{index + 1}:{start + 1}-{end}"
                labels[label] = len(rows)
                rows.append([float(gc_content), float(gc_skew), float(at_skew), float(n_gc)])
                starts.append(start + 1)
                ends.append(end)
                sequence_indexes.append(index + 1)

        out = Form(
            data=np.asarray(rows, dtype=np.float32) if rows else np.zeros((0, 4), dtype=np.float32),
            dims=[window_dim, "statistic"],
            labels={
                window_dim: labels,
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_windows": len(rows),
                "n_sequences": len(sequences),
                "window": int(window),
                "step": int(step),
                "starts": starts,
                "ends": ends,
                "sequence_indexes": sequence_indexes,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_windows": len(rows),
            "n_sequences": len(sequences),
            "window": int(window),
            "step": int(step),
        }
        print(f"[sequence_gc_skew_profile] {len(rows)} windows over {len(sequences)} sequences")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
