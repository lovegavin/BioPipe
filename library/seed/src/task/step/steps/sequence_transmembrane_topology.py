"""Transmembrane topology from hydrophobic segments and loop charges.

``sequence_tm_segments`` answers where the membrane spans are; this operator
answers which side of the membrane each segment faces.  The positive-inside
rule orients the first helix from the net charge of the N-terminal loop, then
the sides alternate along the chain.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.sequence_tm_segments import hydropathy_scores, tm_segments

_STATISTICS = ("start", "end", "length", "mean_hydropathy", "side_code")
_POSITIVE = frozenset("KR")
_NEGATIVE = frozenset("DE")


def loop_charge(sequence: str, start: int, end: int) -> float:
    """Net charge of ``sequence[start:end]`` (1-based inclusive bounds)."""

    lower = max(int(start) - 1, 0)
    upper = min(int(end), len(sequence))
    if upper <= lower:
        return 0.0
    charge = 0.0
    for residue in sequence[lower:upper]:
        if residue in _POSITIVE:
            charge += 1.0
        elif residue in _NEGATIVE:
            charge -= 1.0
    return charge


def topology_rows(
    sequence: str,
    *,
    window: int = 19,
    threshold: float = 1.6,
    min_length: int = 12,
) -> tuple[list[dict], dict]:
    """Assign a membrane side to every detected transmembrane segment."""

    scores = hydropathy_scores(sequence, "sequence_transmembrane_topology")
    segments = tm_segments(
        scores, window=window, threshold=threshold, min_length=min_length
    )
    if not segments:
        raise StepError(
            "sequence_transmembrane_topology: no transmembrane segment reaches "
            "the threshold; topology needs at least one hydrophobic span"
        )

    n_terminal = loop_charge(sequence, 1, segments[0]["start"] - 1)
    first_inside = n_terminal >= 0.0
    rows: list[dict] = []
    for index, segment in enumerate(segments):
        inside = (index % 2 == 0) == first_inside
        rows.append(
            {
                "start": int(segment["start"]),
                "end": int(segment["end"]),
                "length": int(segment["length"]),
                "mean_hydropathy": float(segment["mean_hydropathy"]),
                "side_code": 1.0 if inside else 0.0,
                "side": "in" if inside else "out",
            }
        )
    loops = []
    for index, row in enumerate(rows):
        previous = rows[index - 1]["end"] if index else 0
        loops.append(loop_charge(sequence, previous + 1, row["start"] - 1))
    summary = {
        "n_segments": len(rows),
        "topology": "".join("in" if row["side_code"] else "out" for row in rows),
        "n_terminal_charge": n_terminal,
        "loop_charges": loops,
        "first_side_inside": first_inside,
    }
    return rows, summary


class SequenceTransmembraneTopologyStep(Step):
    """Assign inside/outside sides to transmembrane segments."""

    provider = "operon-core"
    parameters_file = (
        "sequence_transmembrane_topology."
        "SequenceTransmembraneTopologyStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_transmembrane_topology",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Transmembrane topology",
        "description": (
            "Detect transmembrane segments with the Kyte-Doolittle window and "
            "assign each one to the inside or outside face using the "
            "positive-inside rule on the flanking loops."
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
                        "encoders": {"type": "object", "optional": True},
                        "representation": {"type": "string", "const": "sequence_codes"},
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
        threshold = float(params.get("threshold", 1.6))
        min_length = int(params.get("min_length") or 12)
        out_name = str(params.get("output", "topology")) or "topology"

        if window % 2 == 0 or window < 9 or window > 25:
            raise StepError(
                "sequence_transmembrane_topology: window must be an odd integer "
                "between 9 and 25"
            )
        if threshold < -5.0 or threshold > 5.0:
            raise StepError(
                "sequence_transmembrane_topology: threshold must be between -5 and 5"
            )
        if min_length < 5 or min_length > 50:
            raise StepError(
                "sequence_transmembrane_topology: min_length must be between 5 and 50"
            )

        sequences = decode_sequences(inputs[0], sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_transmembrane_topology: the sequence form is empty")
        if len(sequences) != 1:
            raise StepError(
                "sequence_transmembrane_topology: expected exactly one sequence, "
                f"got {len(sequences)}"
            )
        sequence = str(sequences[0]).strip().upper()
        if not sequence:
            raise StepError("sequence_transmembrane_topology: the sequence is empty")

        rows, summary = topology_rows(
            sequence, window=window, threshold=threshold, min_length=min_length
        )
        labels = {f"tm{index + 1}": index for index in range(len(rows))}
        data = np.asarray(
            [
                [
                    float(row["start"]),
                    float(row["end"]),
                    float(row["length"]),
                    row["mean_hydropathy"],
                    row["side_code"],
                ]
                for row in rows
            ],
            dtype=np.float32,
        )
        ctx[out_name] = Form(
            data=data,
            dims=["segment", "statistic"],
            labels={
                "segment": labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "n_segments": summary["n_segments"],
                "topology": summary["topology"],
                "sides": [row["side"] for row in rows],
                "n_terminal_charge": summary["n_terminal_charge"],
                "loop_charges": summary["loop_charges"],
                "window": window,
                "threshold": threshold,
                "min_length": min_length,
            },
        )
        self._export_data = {
            "n_segments": summary["n_segments"],
            "topology": summary["topology"],
            "n_terminal_charge": summary["n_terminal_charge"],
            "loop_charges": summary["loop_charges"],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
