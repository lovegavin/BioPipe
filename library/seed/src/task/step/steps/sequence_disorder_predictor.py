"""Sequence disorder propensity from charge and composition."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


from src.task.step.steps._sequence_common import decode_sequences

_DISORDER = frozenset("ARGQSEKP")
_ORDER = frozenset("WCFIYVL")


def residue_scores(sequence: str) -> np.ndarray:
    """Return a per-residue disorder propensity in [-1, 1]."""

    values = []
    for residue in str(sequence).upper():
        if residue in _DISORDER:
            values.append(1.0)
        elif residue in _ORDER:
            values.append(-1.0)
        elif residue.isalpha():
            values.append(0.0)
        else:
            raise StepError(
                f"sequence_disorder_predictor: residue '{residue}' is not an amino acid"
            )
    return np.asarray(values, dtype=np.float64)


def window_mean(scores: np.ndarray, window: int) -> np.ndarray:
    if window < 1:
        raise StepError("sequence_disorder_predictor: window must be at least 1")
    return np.convolve(scores, np.ones(window) / window, mode="valid")


def disorder_segments(
    scores: np.ndarray,
    *,
    window: int = 25,
    threshold: float = 0.0,
    min_length: int = 4,
) -> list[dict]:
    if scores.size == 0:
        raise StepError("sequence_disorder_predictor: the sequence is empty")
    if scores.size < window:
        raise StepError(
            f"sequence_disorder_predictor: sequence is shorter than the window ({scores.size} < {window})"
        )
    means = window_mean(scores, window)
    rows = []
    start = None
    for index, value in enumerate(means):
        hit = value >= threshold
        if hit and start is None:
            start = index
        elif not hit and start is not None:
            rows.append((start, index - 1))
            start = None
    if start is not None:
        rows.append((start, len(means) - 1))
    segments = []
    for first, last in rows:
        residue_start = first + 1
        residue_end = last + window
        length = residue_end - residue_start + 1
        if length < min_length:
            continue
        span = scores[residue_start - 1 : residue_end]
        segments.append(
            {
                "start": residue_start,
                "end": residue_end,
                "length": length,
                "mean_score": float(span.mean()),
                "max_score": float(span.max()),
            }
        )
    return segments


class SequenceDisorderPredictorStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_disorder_predictor.SequenceDisorderPredictorStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_disorder_predictor",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Sequence disorder predictor",
        "category": "Sequence",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False},
            },
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
            raise StepError(
                f"sequence_disorder_predictor: expected exactly one sequence, got {len(sequences)}"
            )
        sequence = sequences[0]
        scores = residue_scores(sequence)
        segments = disorder_segments(
            scores,
            window=int(params.get("window", 25)),
            threshold=float(params.get("threshold", 0.0)),
            min_length=int(params.get("min_length", 4)),
        )
        if not segments:
            raise StepError(
                "sequence_disorder_predictor: no disordered segment reaches the threshold"
            )
        data = np.array(
            [[s["start"], s["end"], s["length"], s["mean_score"], s["max_score"]] for s in segments],
            dtype=np.float32,
        )
        labels = {f"seg{index + 1}": index for index in range(len(segments))}
        ctx[params.get("output", "disorder")] = Form(
            data=data,
            dims=["segment", "statistic"],
            labels={
                "segment": labels,
                "statistic": {"start": 0, "end": 1, "length": 2, "mean_score": 3, "max_score": 4},
            },
            info={
                "missing_code": np.nan,
                "n_segments": len(segments),
                "n_residues": len(sequence),
                "disordered_fraction": float(sum(s["length"] for s in segments) / len(sequence)),
                "window": int(params.get("window", 25)),
                "threshold": float(params.get("threshold", 0.0)),
            },
        )
        self._export_data = {
            "n_segments": len(segments),
            "n_residues": len(sequence),
            "disordered_fraction": float(sum(s["length"] for s in segments) / len(sequence)),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
