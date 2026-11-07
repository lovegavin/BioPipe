"""CpG island scan with GC content and observed/expected CpG criteria."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences


def island_windows(
    sequence: str,
    *,
    window: int = 200,
    step: int = 10,
    gc_min: float = 0.5,
    cpg_oe_min: float = 0.6,
) -> list[tuple[int, int, float, float]]:
    """Return (start, end, gc, observed/expected) windows that satisfy the criteria."""
    text = sequence.upper()
    length = len(text)
    windows: list[tuple[int, int, float, float]] = []
    if length < window:
        return windows
    for start in range(0, length - window + 1, step):
        chunk = text[start : start + window]
        gc = (chunk.count("G") + chunk.count("C")) / window
        cpg = chunk.count("CG")
        expected = chunk.count("C") * chunk.count("G") / window
        ratio = float(cpg) / expected if expected > 0 else 0.0
        if gc >= gc_min and ratio >= cpg_oe_min:
            windows.append((start, start + window, gc, ratio))
    return windows


def merge_windows(windows: list[tuple[int, int, float, float]]) -> list[dict[str, float]]:
    if not windows:
        return []
    merged: list[dict[str, float]] = []
    start, end, gc, ratio = windows[0]
    count = 1
    for next_start, next_end, next_gc, next_ratio in windows[1:]:
        if next_start <= end:
            end = max(end, next_end)
            gc += next_gc
            ratio += next_ratio
            count += 1
            continue
        merged.append({"start": start, "end": end, "gc": gc / count, "cpg_oe": ratio / count, "windows": count})
        start, end, gc, ratio, count = next_start, next_end, next_gc, next_ratio, 1
    merged.append({"start": start, "end": end, "gc": gc / count, "cpg_oe": ratio / count, "windows": count})
    return merged


class SequenceCpgIslandStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_cpg_island.SequenceCpgIslandStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "sequence_cpg_island",
        "kind": "operator",
        "title": "CpG island scan",
        "description": "Sliding-window CpG island detection using GC content and observed/expected CpG ratio, with merged island coordinates.",
        "category": "Machine Learning",
        "icon": "Dna",
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("sequence_cpg_island: a sequence form input is required")
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence") or "sequence")
        position_dim = str(params.get("position_dim", "position") or "position")
        island_dim = str(params.get("island_dim", "island") or "island")
        out_name = str(params.get("output", "islands") or "islands")
        window = params.get("window")
        window = 200 if window is None else window
        step = params.get("step")
        step = 10 if step is None else step
        gc_min = params.get("gc_min")
        gc_min = 0.5 if gc_min is None else gc_min
        cpg_oe_min = params.get("cpg_oe_min")
        cpg_oe_min = 0.6 if cpg_oe_min is None else cpg_oe_min

        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_cpg_island: sequence input expected [{sequence_dim}, {position_dim}], "
                f"got {list(form.dims)}"
            )
        if isinstance(window, bool) or not isinstance(window, int) or not 20 <= window <= 5000:
            raise StepError("sequence_cpg_island: window must be an integer between 20 and 5000")
        if isinstance(step, bool) or not isinstance(step, int) or not 1 <= step <= window:
            raise StepError("sequence_cpg_island: step must be a positive integer not above the window")
        if not isinstance(gc_min, (int, float)) or not 0.0 < float(gc_min) <= 1.0:
            raise StepError("sequence_cpg_island: gc_min must be in (0, 1]")
        if not isinstance(cpg_oe_min, (int, float)) or float(cpg_oe_min) < 0.0:
            raise StepError("sequence_cpg_island: cpg_oe_min must not be negative")

        sequences = decode_sequences(form, sequence_dim, position_dim)
        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        details: list[dict[str, float]] = []
        for index, sequence in enumerate(sequences):
            windows = island_windows(
                sequence, window=int(window), step=int(step), gc_min=float(gc_min), cpg_oe_min=float(cpg_oe_min)
            )
            for island in merge_windows(windows):
                label = f"seq{index + 1}:{int(island['start']) + 1}-{int(island['end'])}"
                labels[label] = len(rows)
                rows.append(
                    [
                        float(island["start"]) + 1.0,
                        float(island["end"]),
                        float(island["end"]) - float(island["start"]),
                        float(island["gc"]),
                        float(island["cpg_oe"]),
                    ]
                )
                details.append({"label": label, "start": int(island["start"]) + 1, "end": int(island["end"])})
        data = np.asarray(rows, dtype=np.float32) if rows else np.zeros((0, 5), dtype=np.float32)
        out = Form(
            data=data,
            dims=[island_dim, "statistic"],
            labels={
                island_dim: labels,
                "statistic": {"start": 0, "end": 1, "length": 2, "gc_content": 3, "cpg_oe": 4},
            },
            info={
                "missing_code": np.nan,
                "n_islands": len(rows),
                "n_sequences": len(sequences),
                "window": int(window),
                "step": int(step),
                "gc_min": float(gc_min),
                "cpg_oe_min": float(cpg_oe_min),
                "islands": details,
                "criterion": "gardiner-garden/frommer",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_islands": len(rows),
            "n_sequences": len(sequences),
            "window": int(window),
            "step": int(step),
            "gc_min": float(gc_min),
            "cpg_oe_min": float(cpg_oe_min),
        }
        print(f"[sequence_cpg_island] {len(sequences)} sequences, {len(rows)} islands")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
