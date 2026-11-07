"""Protein net charge and charge profile."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

_POSITIVE = {"K": 1.0, "R": 1.0, "H": 0.1}
_NEGATIVE = {"D": -1.0, "E": -1.0, "C": -0.1, "Y": -0.1}


def residue_charges(sequence: str) -> np.ndarray:
    values = []
    for residue in str(sequence).upper():
        if residue not in "ACDEFGHIKLMNPQRSTVWY":
            raise StepError(f"sequence_net_charge: residue '{residue}' is not an amino acid")
        values.append(_POSITIVE.get(residue, 0.0) + _NEGATIVE.get(residue, 0.0))
    return np.asarray(values, dtype=np.float64)


def sliding_charge(charges: np.ndarray, window: int) -> np.ndarray:
    if window < 1:
        raise StepError("sequence_net_charge: window must be at least 1")
    return np.convolve(charges, np.ones(window), mode="valid")


class SequenceNetChargeStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_net_charge.SequenceNetChargeStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_net_charge",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Protein net charge",
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
            raise StepError(f"sequence_net_charge: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        charges = residue_charges(sequence)
        window = int(params.get("window", 9))
        if window > len(sequence):
            raise StepError(f"sequence_net_charge: sequence is shorter than the window ({len(sequence)} < {window})")
        profile = sliding_charge(charges, window)
        if profile.size == 0:
            raise StepError(f"sequence_net_charge: sequence is shorter than the window ({len(sequence)} < {window})")
        data = np.array([[float(charges.sum()), float(charges.mean()), float(profile.max()), float(profile.min())]], dtype=np.float32)
        ctx[params.get("output", "charge")] = Form(
            data=data,
            dims=["sequence", "statistic"],
            labels={"sequence": {"net": 0}, "statistic": {"net_charge": 0, "mean_charge": 1, "max_window": 2, "min_window": 3}},
            info={"missing_code": np.nan, "length": len(sequence), "window": window, "positive": int(sum(1 for r in sequence if r in "KRH")), "negative": int(sum(1 for r in sequence if r in "DECY"))},
        )
        self._export_data = {"net_charge": float(charges.sum()), "length": len(sequence)}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
