"""Helical hydrophobic moment."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

# Eisenberg consensus hydrophobicity scale.
_EISENBERG = {"A": 0.62, "R": -2.53, "N": -0.78, "D": -0.90, "C": 0.29, "Q": -0.85, "E": -0.74, "G": 0.48, "H": -0.40, "I": 1.38, "L": 1.06, "K": -1.50, "M": 0.64, "F": 1.19, "P": 0.12, "S": -0.18, "T": -0.05, "W": 0.81, "Y": 0.26, "V": 1.08}
_TURN = np.deg2rad(100.0)


def hydrophobic_moment(sequence: str) -> tuple[float, float, np.ndarray]:
    """Return the mean moment, the mean hydrophobicity and per-window moments."""

    values = []
    for residue in str(sequence).upper():
        if residue not in _EISENBERG:
            raise StepError(f"sequence_hydrophobic_moment: residue '{residue}' is outside the Eisenberg scale")
        values.append(_EISENBERG[residue])
    scores = np.asarray(values, dtype=np.float64)
    if scores.size < 9:
        raise StepError(f"sequence_hydrophobic_moment: at least nine residues are required, got {scores.size}")
    windows = scores.size - 8
    moments = np.zeros(windows)
    for start in range(windows):
        window = scores[start:start + 9]
        angles = np.arange(9) * _TURN
        moments[start] = float(abs(np.sum(window * np.exp(1j * angles))))
    return float(moments.mean()), float(scores.mean()), moments


class SequenceHydrophobicMomentStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_hydrophobic_moment.SequenceHydrophobicMomentStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_hydrophobic_moment",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Helical hydrophobic moment",
        "category": "Sequence",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], params["sequence_dim"], params["position_dim"])
        if len(sequences) != 1:
            raise StepError(f"sequence_hydrophobic_moment: expected exactly one sequence, got {len(sequences)}")
        mean_moment, mean_hydrophobicity, moments = hydrophobic_moment(sequences[0])
        index = int(np.argmax(moments))
        data = np.array([[moments[index], index + 1, mean_moment, mean_hydrophobicity]], dtype=np.float32)
        ctx[params.get("output", "moment")] = Form(
            data=data,
            dims=["sequence", "statistic"],
            labels={"sequence": {"seq1": 0}, "statistic": {"max_moment": 0, "max_start": 1, "mean_moment": 2, "mean_hydrophobicity": 3}},
            info={"missing_code": np.nan, "n_windows": int(moments.size), "length": len(sequences[0]), "max_moment": float(moments[index]), "max_start": index + 1},
        )
        self._export_data = {"max_moment": float(moments[index]), "mean_moment": mean_moment}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
