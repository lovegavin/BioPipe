"""Per-position hydrophobicity profiles from sliding-window GRAVY."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences


KYTE_DOOLITTLE = {
    "A": 1.8,
    "R": -4.5,
    "N": -3.5,
    "D": -3.5,
    "C": 2.5,
    "Q": -3.5,
    "E": -3.5,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "L": 3.8,
    "K": -3.9,
    "M": 1.9,
    "F": 2.8,
    "P": -1.6,
    "S": -0.8,
    "T": -0.7,
    "W": -0.9,
    "Y": -1.3,
    "V": 4.2,
}


def window_profile(sequence: str, window: int = 9) -> np.ndarray:
    """Sliding-window Kyte-Doolittle mean per position, NaN outside the full window."""

    if window < 1:
        raise StepError("sequence_hydrophobicity_profile: window must be at least 1")
    values = np.full(len(sequence), np.nan, dtype=np.float64)
    if len(sequence) < window:
        return values
    scores = np.array([KYTE_DOOLITTLE.get(residue.upper(), np.nan) for residue in sequence])
    if np.isnan(scores).any():
        raise StepError(
            "sequence_hydrophobicity_profile: the sequence contains residues outside the "
            "Kyte-Doolittle scale"
        )
    half = window // 2
    kernel = np.ones(window, dtype=np.float64) / float(window)
    smoothed = np.convolve(scores, kernel, mode="valid")
    start = half if window % 2 == 1 else half - 1
    values[start : start + len(smoothed)] = smoothed
    return values


def hydrophobic_segments(profile: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    """1-based inclusive ranges whose window mean is at least the threshold."""

    segments: list[tuple[int, int]] = []
    start = None
    for index, value in enumerate(profile):
        positive = bool(np.isfinite(value) and value >= threshold)
        if positive and start is None:
            start = index
        elif not positive and start is not None:
            segments.append((start + 1, index))
            start = None
    if start is not None:
        segments.append((start + 1, len(profile)))
    return segments


class SequenceHydrophobicityProfileStep(Step):
    """Sliding-window Kyte-Doolittle profile per sequence position."""

    provider = "operon-core"

    parameters_file = "sequence_hydrophobicity_profile.SequenceHydrophobicityProfileStep.parameters.json"


    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_hydrophobicity_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Sequence hydrophobicity profile",
        "description": (
            "Compute a sliding-window Kyte-Doolittle hydrophobicity profile for each protein "
            "sequence and report hydrophobic segments above a threshold."
        ),
        "category": "Machine Learning",
        "icon": "ChartLine",
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
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet": {"type": "string", "const": "protein"},
                    },
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
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        window = int(params.get("window", 9))
        threshold = float(params.get("threshold", 1.6))
        output = str(params.get("output", "profile"))

        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_hydrophobicity_profile: the input must have dims "
                f"[{sequence_dim}, {position_dim}], got {list(form.dims)}"
            )
        if window < 3:
            raise StepError(
                "sequence_hydrophobicity_profile: window must be at least 3 residues"
            )
        if window % 2 == 0:
            raise StepError(
                "sequence_hydrophobicity_profile: window must be an odd number of residues"
            )
        if not np.isfinite(threshold):
            raise StepError(
                "sequence_hydrophobicity_profile: threshold must be a finite number"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_hydrophobicity_profile: the input contains no sequence")
        if any(len(sequence) < window for sequence in sequences):
            raise StepError(
                "sequence_hydrophobicity_profile: every sequence must be at least as long as "
                f"the window ({window} residues)"
            )

        rows = np.full((len(sequences), max(len(s) for s in sequences)), np.nan, dtype=np.float32)
        segments: dict[int, list[list[int]]] = {}
        stats = []
        for index, sequence in enumerate(sequences):
            profile = window_profile(sequence, window)
            rows[index, : len(sequence)] = profile.astype(np.float32)
            finite = profile[np.isfinite(profile)]
            found = hydrophobic_segments(profile, threshold)
            segments[str(index + 1)] = [[start, end] for start, end in found]
            stats.append(
                {
                    "sequence": sequence,
                    "length": len(sequence),
                    "mean": round(float(finite.mean()), 4) if finite.size else None,
                    "max": round(float(finite.max()), 4) if finite.size else None,
                    "min": round(float(finite.min()), 4) if finite.size else None,
                    "segments": segments[str(index + 1)],
                }
            )

        labels = {
            sequence_dim: dict(getattr(form, "labels", {}).get(sequence_dim, {}))
            or {f"seq{index + 1}": index for index in range(len(sequences))},
            position_dim: {
                str(position + 1): position
                for position in range(rows.shape[1])
            },
        }
        info = {
            "missing_code": np.nan,
            "window": window,
            "threshold": threshold,
            "scale": "kyte-doolittle",
            "sequences": stats,
            "n_sequences": len(sequences),
        }
        out = Form(data=rows, dims=[sequence_dim, position_dim], labels=labels, info=info)
        out.validate()
        ctx[output] = out
        self._export_data = {
            "n_sequences": len(sequences),
            "window": window,
            "threshold": threshold,
            "segments": segments,
            "sequences": [item["sequence"] for item in stats],
            "max_profile": [item["max"] for item in stats],
        }
        print(
            f"[sequence_hydrophobicity_profile] sequences={len(sequences)} window={window} "
            f"segments={sum(len(value) for value in segments.values())}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})


__all__ = ["SequenceHydrophobicityProfileStep", "hydrophobic_segments", "window_profile"]
