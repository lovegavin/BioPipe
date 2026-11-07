"""Sequence complexity metrics for low-complexity and repeat detection."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_STATISTICS = (
    "length",
    "entropy_1",
    "entropy_2",
    "entropy_3",
    "normalized_entropy_3",
    "linguistic_complexity",
    "low_complexity_fraction",
)
_ALPHABET = 20


def shannon_entropy(sequence: str, k: int) -> float:
    """Return the Shannon entropy in bits of the k-mer distribution of one sequence."""
    if not sequence:
        return float("nan")
    if k <= 0 or k > len(sequence):
        return float("nan")
    counts = Counter(sequence[index : index + k] for index in range(len(sequence) - k + 1))
    total = sum(counts.values())
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def linguistic_complexity(sequence: str, k_max: int = 3) -> float:
    """Return the mean ratio of observed to possible k-mers for k = 1..k_max."""
    if not sequence:
        return float("nan")
    ratios: list[float] = []
    for k in range(1, k_max + 1):
        if k > len(sequence):
            break
        observed = len({sequence[index : index + k] for index in range(len(sequence) - k + 1)})
        possible = min(_ALPHABET**k, len(sequence) - k + 1)
        ratios.append(observed / possible)
    return float(np.mean(ratios)) if ratios else float("nan")


def low_complexity_fraction(sequence: str, window: int, threshold: float) -> float:
    """Return the fraction of windows whose 1-mer entropy is at or below ``threshold``."""
    if not sequence:
        return float("nan")
    if len(sequence) <= window:
        return 1.0 if shannon_entropy(sequence, 1) <= threshold else 0.0
    low = 0
    total = 0
    for start in range(0, len(sequence) - window + 1):
        total += 1
        if shannon_entropy(sequence[start : start + window], 1) <= threshold:
            low += 1
    return low / total if total else float("nan")


def complexity_row(sequence: str, *, window: int = 20, threshold: float = 2.0) -> dict[str, float]:
    """Return every complexity statistic for one sequence."""
    return {
        "length": float(len(sequence)),
        "entropy_1": shannon_entropy(sequence, 1),
        "entropy_2": shannon_entropy(sequence, 2),
        "entropy_3": shannon_entropy(sequence, 3),
        "normalized_entropy_3": shannon_entropy(sequence, 3) / math.log2(_ALPHABET**3)
        if sequence
        else float("nan"),
        "linguistic_complexity": linguistic_complexity(sequence, 3),
        "low_complexity_fraction": low_complexity_fraction(sequence, window, threshold),
    }


class SequenceComplexityStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_complexity.SequenceComplexityStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_complexity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Sequence Complexity",
        "description": (
            "Measure protein sequence complexity with k-mer Shannon entropy, linguistic "
            "complexity and the fraction of low-complexity windows, useful for filtering "
            "repeat-rich or low-entropy designed sequences."
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
                        "missing_code": {"type": "number"},
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
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        form = inputs[0] if inputs else None
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        output = str(params.get("output", "output"))
        window = int(params.get("window", 20))
        if not 5 <= window <= 200:
            raise StepError("sequence_complexity: window must be between 5 and 200 residues")
        threshold = float(params.get("low_complexity_entropy", 2.0))
        if not 0.0 <= threshold <= math.log2(_ALPHABET):
            raise StepError(
                "sequence_complexity: low_complexity_entropy must be between 0 and 4.32 bits"
            )
        if form is None or len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_complexity: a sequence form with dims [{sequence_dim}, {position_dim}] is required"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_complexity: the input has no sequences")
        if any(not sequence for sequence in sequences):
            raise StepError("sequence_complexity: every sequence must contain at least one residue")

        names = list(form.labels.get(sequence_dim, {}).keys()) or [
            f"sequence{index + 1}" for index in range(len(sequences))
        ]
        rows = [complexity_row(sequence, window=window, threshold=threshold) for sequence in sequences]
        data = np.asarray([[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32)
        out = Form(
            data=data,
            dims=[sequence_dim, "statistic"],
            labels={
                sequence_dim: {name: index for index, name in enumerate(names[: len(sequences)])},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(sequences),
                "window": window,
                "low_complexity_entropy": threshold,
                "alphabet": _ALPHABET,
                "entropy_unit": "bits",
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "n_sequences": len(sequences),
            "mean_entropy_1": float(np.mean(data[:, 1])),
            "mean_linguistic_complexity": float(np.mean(data[:, 5])),
            "lowest_complexity": names[int(np.argmin(data[:, 5]))] if names else None,
        }
        print(
            f"[sequence_complexity] {len(sequences)} sequences, "
            f"mean entropy {np.mean(data[:, 1]):.2f} bits, "
            f"mean complexity {np.mean(data[:, 5]):.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
