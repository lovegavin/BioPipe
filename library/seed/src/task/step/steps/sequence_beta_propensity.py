"""Beta-sheet propensity from Chou-Fasman frequencies."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

_PBETA = {"A": 0.83, "R": 0.93, "N": 0.89, "D": 0.54, "C": 1.19, "Q": 1.10, "E": 0.37, "G": 0.75, "H": 0.87, "I": 1.60, "L": 1.30, "K": 0.74, "M": 1.05, "F": 1.38, "P": 0.55, "S": 0.75, "T": 1.19, "W": 1.37, "Y": 1.47, "V": 1.70}


def beta_scores(sequence: str) -> np.ndarray:
    values = []
    for residue in str(sequence).upper():
        if residue not in _PBETA:
            raise StepError(f"sequence_beta_propensity: residue '{residue}' is outside the Chou-Fasman table")
        values.append(_PBETA[residue])
    return np.asarray(values, dtype=np.float64)


def beta_hotspots(scores: np.ndarray, *, window: int = 5, threshold: float = 1.05, min_length: int = 4) -> list[dict]:
    if scores.size < window:
        raise StepError(f"sequence_beta_propensity: sequence is shorter than the window ({scores.size} < {window})")
    means = np.convolve(scores, np.ones(window) / window, mode="valid")
    spans = []
    start = None
    for index, value in enumerate(means):
        hit = value >= threshold
        if hit and start is None:
            start = index
        elif not hit and start is not None:
            spans.append((start, index - 1))
            start = None
    if start is not None:
        spans.append((start, len(means) - 1))
    rows = []
    for first, last in spans:
        residue_start = first + 1
        residue_end = last + window
        length = residue_end - residue_start + 1
        if length < min_length:
            continue
        rows.append({"start": residue_start, "end": residue_end, "length": length, "mean_score": float(means[first:last + 1].mean()), "max_score": float(means[first:last + 1].max())})
    return rows


class SequenceBetaPropensityStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_beta_propensity.SequenceBetaPropensityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_beta_propensity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Beta-sheet propensity",
        "category": "Sequence",
        "icon": "ChartBar",
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
            raise StepError(f"sequence_beta_propensity: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        scores = beta_scores(sequence)
        rows = beta_hotspots(scores, window=int(params.get("window", 5)), threshold=float(params.get("threshold", 1.05)), min_length=int(params.get("min_length", 4)))
        if not rows:
            raise StepError("sequence_beta_propensity: no beta-sheet hotspot reaches the threshold")
        data = np.array([[r["start"], r["end"], r["length"], r["mean_score"], r["max_score"]] for r in rows], dtype=np.float32)
        ctx[params.get("output", "hotspots")] = Form(
            data=data,
            dims=["hotspot", "statistic"],
            labels={"hotspot": {f"hotspot{i + 1}": i for i in range(len(rows))}, "statistic": {"start": 0, "end": 1, "length": 2, "mean_score": 3, "max_score": 4}},
            info={"missing_code": np.nan, "n_hotspots": len(rows), "n_residues": len(sequence), "mean_propensity": float(scores.mean()), "window": int(params.get("window", 5)), "threshold": float(params.get("threshold", 1.05))},
        )
        self._export_data = {"n_hotspots": len(rows)}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
