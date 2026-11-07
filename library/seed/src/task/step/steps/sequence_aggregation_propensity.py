"""Aggregation propensity from the AGGRESCAN a3v scale."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

_A3V = {"A": -0.144, "C": 1.114, "D": -1.096, "E": -0.592, "F": 0.945, "G": -0.514, "H": -0.341, "I": 0.853, "K": -1.102, "L": 0.755, "M": 0.576, "N": -0.724, "P": 0.557, "Q": -0.614, "R": -0.632, "S": -0.486, "T": -0.376, "V": 0.671, "W": 0.705, "Y": 0.573}


def propensity_scores(sequence: str) -> np.ndarray:
    values = []
    for residue in str(sequence).upper():
        if residue not in _A3V:
            raise StepError(f"sequence_aggregation_propensity: residue '{residue}' is outside the a3v scale")
        values.append(_A3V[residue])
    return np.asarray(values, dtype=np.float64)


def window_scores(scores: np.ndarray, window: int) -> np.ndarray:
    if window < 1:
        raise StepError("sequence_aggregation_propensity: window must be at least 1")
    return np.convolve(scores, np.ones(window) / window, mode="valid")


def hotspot_segments(scores: np.ndarray, *, window: int = 5, threshold: float = 0.35, min_length: int = 3) -> list[dict]:
    if scores.size < window:
        raise StepError(f"sequence_aggregation_propensity: sequence is shorter than the window ({scores.size} < {window})")
    means = window_scores(scores, window)
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
    hotspots = []
    for first, last in spans:
        residue_start = first + 1
        residue_end = last + window
        length = residue_end - residue_start + 1
        if length < min_length:
            continue
        hotspots.append({"start": residue_start, "end": residue_end, "length": length, "mean_score": float(means[first:last + 1].mean()), "max_score": float(means[first:last + 1].max())})
    return hotspots


class SequenceAggregationPropensityStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_aggregation_propensity.SequenceAggregationPropensityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_aggregation_propensity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Aggregation propensity",
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
        if len(sequences) != 1:
            raise StepError(f"sequence_aggregation_propensity: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        scores = propensity_scores(sequence)
        hotspots = hotspot_segments(scores, window=int(params.get("window", 5)), threshold=float(params.get("threshold", 0.35)), min_length=int(params.get("min_length", 3)))
        if not hotspots:
            raise StepError("sequence_aggregation_propensity: no aggregation hotspot reaches the threshold")
        for hotspot in hotspots:
            hotspot["motif"] = sequence[hotspot["start"] - 1 : hotspot["end"]]
        data = np.array([[h["start"], h["end"], h["length"], h["mean_score"], h["max_score"]] for h in hotspots], dtype=np.float32)
        labels = {f"hotspot{index + 1}": index for index in range(len(hotspots))}
        ctx[params.get("output", "hotspots")] = Form(
            data=data,
            dims=["hotspot", "statistic"],
            labels={"hotspot": labels, "statistic": {"start": 0, "end": 1, "length": 2, "mean_score": 3, "max_score": 4}},
            info={"missing_code": np.nan, "n_hotspots": len(hotspots), "n_residues": len(sequence), "mean_propensity": float(scores.mean()), "max_propensity": float(scores.max()), "window": int(params.get("window", 5)), "threshold": float(params.get("threshold", 0.35)), "motifs": [h["motif"] for h in hotspots]},
        )
        self._export_data = {"n_hotspots": len(hotspots), "mean_propensity": float(scores.mean())}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
