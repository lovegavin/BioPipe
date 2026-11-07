"""Transmembrane helix segments from Kyte-Doolittle hydropathy windows.

A residue window is a candidate membrane span when its mean Kyte-Doolittle
hydropathy reaches the classic threshold of 1.6.  Consecutive candidate windows
are merged into segments and short segments are dropped, so the output lists
the hydrophobic spans of a sequence together with their hydropathy.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.sequence_hydrophobicity_profile import KYTE_DOOLITTLE

_STATISTICS = ("start", "end", "length", "mean_hydropathy", "max_hydropathy")


def hydropathy_scores(sequence: str, operator: str = "sequence_tm_segments") -> np.ndarray:
    """Map a protein sequence onto the Kyte-Doolittle scale."""

    unknown = sorted({residue for residue in sequence if residue not in KYTE_DOOLITTLE})
    if unknown:
        raise StepError(
            f"{operator}: residues outside the Kyte-Doolittle scale: "
            f"{''.join(unknown)}"
        )
    return np.array([KYTE_DOOLITTLE[residue] for residue in sequence], dtype=np.float64)


def window_means(scores: np.ndarray, window: int) -> np.ndarray:
    """Mean hydropathy of every fully contained window."""

    if scores.size < window:
        return np.zeros(0, dtype=np.float64)
    kernel = np.ones(window, dtype=np.float64) / float(window)
    return np.convolve(scores, kernel, mode="valid")


def tm_segments(
    scores: np.ndarray,
    *,
    window: int,
    threshold: float,
    min_length: int,
) -> list[dict]:
    """Return the merged candidate spans longer than ``min_length``."""

    means = window_means(scores, window)
    hits = np.flatnonzero(means >= threshold)
    if hits.size == 0:
        return []
    runs: list[tuple[int, int]] = []
    start = int(hits[0])
    previous = int(hits[0])
    for index in hits[1:]:
        current = int(index)
        if current == previous + 1:
            previous = current
            continue
        runs.append((start, previous))
        start = previous = current
    runs.append((start, previous))
    records: list[dict] = []
    for first, last in runs:
        residue_start = first
        residue_stop = last + window - 1
        length = residue_stop - residue_start + 1
        if length < min_length:
            continue
        span = scores[residue_start : residue_stop + 1]
        records.append(
            {
                "start": residue_start + 1,
                "end": residue_stop + 1,
                "length": length,
                "mean_hydropathy": float(span.mean()),
                "max_hydropathy": float(span.max()),
            }
        )
    return records


class SequenceTmSegmentsStep(Step):
    """Membrane-span candidates from sliding-window hydropathy."""

    provider = "operon-core"

    parameters_file = (
        "sequence_tm_segments.SequenceTmSegmentsStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_tm_segments",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Transmembrane helix segments",
        "description": (
            "Score a protein sequence with Kyte-Doolittle hydropathy windows, "
            "merge windows above the membrane threshold into segments and "
            "report their ranges and hydropathy."
        ),
        "category": "Sequence",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "missing_code": {"type": ["number", "null"]},
                        "representation": {
                            "type": "string",
                            "const": "sequence_codes",
                        },
                        "alphabet_map": {"type": "object"},
                        "unknown_code": {"type": "integer"},
                    },
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
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")).strip() or "sequence"
        position_dim = str(params.get("position_dim", "position")).strip() or "position"
        window = int(params.get("window") or 19)
        threshold = float(params.get("threshold") or 1.6)
        min_length = int(params.get("min_length") or 12)
        out_name = params.get("output", self.name)

        if window % 2 == 0 or not 9 <= window <= 25:
            raise StepError(
                "sequence_tm_segments: window must be an odd integer between 9 "
                "and 25"
            )
        if not -5.0 <= threshold <= 5.0:
            raise StepError(
                "sequence_tm_segments: threshold must be between -5 and 5"
            )
        if not 5 <= min_length <= 50:
            raise StepError(
                "sequence_tm_segments: min_length must be between 5 and 50"
            )
        form = inputs[0]
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_tm_segments: the input form has no sequences")
        records_all: list[list[dict]] = []
        for index, sequence in enumerate(sequences):
            if not sequence:
                raise StepError(
                    f"sequence_tm_segments: sequence {index} is empty"
                )
            if len(sequence) < window:
                raise StepError(
                    "sequence_tm_segments: sequence "
                    f"{index} is shorter than the window ({len(sequence)} < "
                    f"{window})"
                )
            scores = hydropathy_scores(sequence)
            records_all.append(
                tm_segments(
                    scores,
                    window=window,
                    threshold=threshold,
                    min_length=min_length,
                )
            )
        flat = [(index, record) for index, records in enumerate(records_all) for record in records]
        if not flat:
            raise StepError(
                "sequence_tm_segments: no transmembrane segment reaches the "
                f"threshold {threshold:g}"
            )
        order = [label for label, _ in sorted(form.labels[sequence_dim].items(), key=lambda item: item[1])]
        rows = [
            (
                float(record["start"]),
                float(record["end"]),
                float(record["length"]),
                record["mean_hydropathy"],
                record["max_hydropathy"],
            )
            for _, record in flat
        ]
        labels = {
            "segment": {
                f"{order[index]}:tm{position + 1}": position
                for position, (index, _) in enumerate(flat)
            },
            "statistic": {
                name: position for position, name in enumerate(_STATISTICS)
            },
        }
        form_out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["segment", "statistic"],
            labels=labels,
            info={
                "window": window,
                "threshold": threshold,
                "min_length": min_length,
                "n_segments": len(flat),
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_segments": len(flat),
            "window": window,
            "threshold": threshold,
        }
        print(f"[{self.name}] {len(flat)} transmembrane segment(s)")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
