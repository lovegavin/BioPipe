"""Tandem repeat finder for nucleotide sequences.

The scan walks the sequence once, looking for the shortest period that extends
the furthest from the current position, so repeats are reported as
non-overlapping tandem arrays with their 1-based start, period and copy count.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.forms.form import Form
from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_NUCLEOTIDES = set("ACGTUN")
_STATISTICS = ("start", "period", "copies", "length")


def repeat_rows(sequence: str, *, min_period: int = 2, max_period: int = 6, min_copies: int = 2):
    letters = sequence.upper()
    rows: list[tuple[int, int, int, int]] = []
    position = 0
    length = len(letters)
    while position < length:
        best: tuple[int, int, int, int] | None = None
        for period in range(min_period, max_period + 1):
            cursor = position + period
            while cursor < length and letters[cursor] == letters[cursor - period]:
                cursor += 1
            span = cursor - position
            copies = span // period
            if copies >= min_copies:
                candidate = (position + 1, period, copies, copies * period)
                if best is None or candidate[3] > best[3] or (candidate[3] == best[3] and period < best[1]):
                    best = candidate
        if best is None:
            position += 1
        else:
            rows.append(best)
            position += best[3]
    return rows


class SequenceRepeatFinderStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_repeat_finder.SequenceRepeatFinderStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_repeat_finder",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Tandem repeat finder",
        "description": "Non-overlapping tandem repeats with period and copy counts.",
        "category": "Machine Learning",
        "icon": "ListBullets",
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
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
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
        form = inputs[0]
        sequence_dim = str(ctx.step_params.get("sequence_dim") or "sequence")
        position_dim = str(ctx.step_params.get("position_dim") or "position")
        repeat_dim = str(ctx.step_params.get("repeat_dim") or "repeat")
        min_period = ctx.step_params.get("min_period", 2)
        max_period = ctx.step_params.get("max_period", 6)
        min_copies = ctx.step_params.get("min_copies", 2)
        out_name = str(ctx.step_params.get("output") or "repeats")

        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_repeat_finder: a sequence form with dims [{sequence_dim}, {position_dim}] is required, got {list(form.dims)}"
            )
        for value, label in ((min_period, "min_period"), (max_period, "max_period"), (min_copies, "min_copies")):
            if isinstance(value, bool) or not isinstance(value, int):
                raise StepError(f"sequence_repeat_finder: {label} must be an integer")
        if min_period < 1:
            raise StepError("sequence_repeat_finder: min_period must be at least 1")
        if max_period < min_period:
            raise StepError("sequence_repeat_finder: max_period must not be smaller than min_period")
        if min_copies < 2:
            raise StepError("sequence_repeat_finder: min_copies must be at least 2")
        if repeat_dim in (sequence_dim, position_dim):
            raise StepError("sequence_repeat_finder: repeat_dim must differ from the sequence and position dims")

        sequences = decode_sequences(form, sequence_dim, position_dim)
        rows: list[tuple[float, ...]] = []
        names: list[str] = []
        for index, sequence in enumerate(sequences):
            unknown = sorted({letter for letter in sequence.upper() if letter not in _NUCLEOTIDES})
            if unknown:
                raise StepError(
                    f"sequence_repeat_finder: sequence {index + 1} contains non-nucleotide residues: {''.join(unknown)}"
                )
            for start, period, copies, length in repeat_rows(
                sequence, min_period=min_period, max_period=max_period, min_copies=min_copies
            ):
                rows.append((float(start), float(period), float(copies), float(length)))
                names.append(f"seq{index + 1}:{start}")
        data = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        out = Form(
            data=data,
            dims=[repeat_dim, "statistic"],
            labels={
                repeat_dim: {name: position for position, name in enumerate(names)},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "n_sequences": len(sequences),
                "n_repeats": len(rows),
                "min_period": min_period,
                "max_period": max_period,
                "min_copies": min_copies,
                "missing_code": np.nan,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(sequences),
            "n_repeats": len(rows),
            "min_period": min_period,
            "max_period": max_period,
            "min_copies": min_copies,
        }
        print(f"[sequence_repeat_finder] {len(rows)} tandem repeats in {len(sequences)} sequences")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
