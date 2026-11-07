"""Isoelectric point from standard pKa values."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

# EMBOSS-style pKa set; termini included through explicit offsets.
_PKA = {"Cterm": 3.6, "Nterm": 8.6, "C": 8.5, "D": 3.9, "E": 4.1, "H": 6.5, "K": 10.8, "R": 12.5, "Y": 10.1}


def net_charge(sequence: str, ph: float) -> float:
    """Return the net charge of a sequence at a given pH."""

    if not sequence:
        raise StepError("sequence_isoelectric_point: the sequence is empty")
    positive = 1.0 / (1.0 + 10.0 ** (ph - _PKA["Nterm"]))
    positive += sequence.count("K") / (1.0 + 10.0 ** (ph - _PKA["K"]))
    positive += sequence.count("R") / (1.0 + 10.0 ** (ph - _PKA["R"]))
    positive += sequence.count("H") / (1.0 + 10.0 ** (ph - _PKA["H"]))
    negative = 1.0 / (1.0 + 10.0 ** (_PKA["Cterm"] - ph))
    for residue in "DECY":
        negative += sequence.count(residue) / (1.0 + 10.0 ** (_PKA[residue] - ph))
    return float(positive - negative)


def isoelectric_point(sequence: str, *, low: float = 0.0, high: float = 14.0, tolerance: float = 1e-6) -> float:
    """Bisect the net charge for the pH at which it vanishes."""

    if not any(residue in "KRHDECY" for residue in sequence):
        raise StepError("sequence_isoelectric_point: the sequence carries no titratable residue")
    for _ in range(200):
        middle = 0.5 * (low + high)
        charge = net_charge(sequence, middle)
        if charge > 0:
            low = middle
        else:
            high = middle
        if high - low < tolerance:
            break
    return float(0.5 * (low + high))


class SequenceIsoelectricPointStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_isoelectric_point.SequenceIsoelectricPointStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_isoelectric_point",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Isoelectric point",
        "category": "Sequence",
        "icon": "ChartLine",
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
        pI = [isoelectric_point(sequence) for sequence in sequences]
        charge = [net_charge(sequence, float(params.get("ph", 7.0))) for sequence in sequences]
        data = np.array([[value, charge[i]] for i, value in enumerate(pI)], dtype=np.float32)
        ctx[params.get("output", "isoelectric_point")] = Form(
            data=data,
            dims=["sequence", "statistic"],
            labels={"sequence": {f"seq{i + 1}": i for i in range(len(pI))}, "statistic": {"pI": 0, "charge_at_ph": 1}},
            info={"missing_code": np.nan, "ph": float(params.get("ph", 7.0)), "n_sequences": len(pI), "pI": pI},
        )
        self._export_data = {"n_sequences": len(pI), "pI": pI}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
