"""sequence_rna_accessibility: per-base unpaired probabilities from the ensemble."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_ALPHABET = set("ACGUN")


def _load_rna():
    try:
        import RNA
    except ImportError:
        raise StepError(
            "sequence_rna_accessibility: the ViennaRNA Python bindings are required; "
            "install them with 'python -m pip install ViennaRNA'"
        ) from None
    return RNA


def pairing_probabilities(sequence: str, temperature: float = 37.0) -> tuple[np.ndarray, float, str]:
    """Return the base-pair probability matrix, MFE energy and MFE structure."""

    clean = sequence.strip().upper().replace("T", "U")
    if not clean:
        raise StepError("sequence_rna_accessibility: the sequence is empty")
    invalid = sorted(set(clean) - _ALPHABET)
    if invalid:
        raise StepError(f"sequence_rna_accessibility: non-RNA residue(s) {invalid}")
    rna = _load_rna()
    parameters = rna.md()
    parameters.temperature = float(temperature)
    compound = rna.fold_compound(clean, parameters)
    compound.pf()
    matrix = np.asarray(compound.bpp(), dtype=float)
    if matrix.shape[0] == len(clean) + 1:
        # ViennaRNA returns 1-based pair probabilities with a zero border.
        matrix = matrix[1 : len(clean) + 1, 1 : len(clean) + 1]
    # ViennaRNA fills the upper triangle only; make the matrix symmetric.
    matrix = matrix + matrix.T
    structure, energy = compound.mfe()
    return matrix, float(energy), str(structure)


def accessibility_rows(matrix: np.ndarray, *, threshold: float = 0.5, min_length: int = 2) -> tuple[np.ndarray, list[dict]]:
    """Return unpaired probabilities and accessible segments."""

    if matrix.shape[0] != matrix.shape[1]:
        raise StepError("sequence_rna_accessibility: the pair-probability matrix must be square")
    if not 0.0 <= threshold <= 1.0:
        raise StepError("sequence_rna_accessibility: threshold must be in [0, 1]")
    if min_length < 1:
        raise StepError("sequence_rna_accessibility: min_length must be at least 1")
    paired = matrix.sum(axis=1)
    unpaired = np.clip(1.0 - paired, 0.0, 1.0)
    segments = []
    start = None
    for index, value in enumerate(unpaired):
        if value >= threshold:
            if start is None:
                start = index
        elif start is not None:
            if index - start >= min_length:
                segments.append({"start": start + 1, "end": index, "length": index - start, "mean_unpaired": float(unpaired[start:index].mean())})
            start = None
    if start is not None and len(unpaired) - start >= min_length:
        segments.append({"start": start + 1, "end": len(unpaired), "length": len(unpaired) - start, "mean_unpaired": float(unpaired[start:].mean())})
    return unpaired, segments


class SequenceRnaAccessibilityStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_rna_accessibility.SequenceRnaAccessibilityStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_rna_accessibility",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 可及性",
        "description": (
            "Compute the Boltzmann ensemble base-pair probabilities with ViennaRNA and "
            "report per-base unpaired probabilities plus accessible single-stranded segments."
        ),
        "category": "Sequence",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["ViennaRNA>=2.6"],
        "dependency_imports": ["RNA"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        if len(sequences) != 1:
            raise StepError(f"sequence_rna_accessibility: expected exactly one sequence, got {len(sequences)}")
        sequence = sequences[0]
        temperature = float(params.get("temperature", 37.0))
        if not 0.0 < temperature <= 100.0:
            raise StepError("sequence_rna_accessibility: temperature must be in (0, 100]")
        matrix, energy, structure = pairing_probabilities(sequence, temperature)
        unpaired, segments = accessibility_rows(
            matrix,
            threshold=float(params.get("threshold", 0.5)),
            min_length=int(params.get("min_length", 2)),
        )
        rows = np.vstack([unpaired, 1.0 - unpaired]).T.astype(np.float32)
        out = str(params.get("output", "accessibility"))
        ctx[out] = Form(
            data=rows,
            dims=["position", "statistic"],
            labels={"position": {f"r{index + 1}": index for index in range(len(unpaired))}, "statistic": {"unpaired_probability": 0, "paired_probability": 1}},
            info={
                "n_residues": int(len(unpaired)),
                "mfe_energy_kcal": energy,
                "mfe_structure": structure,
                "mean_unpaired": float(unpaired.mean()),
                "max_unpaired": float(unpaired.max()),
                "n_accessible_segments": len(segments),
                "accessible_segments": segments,
                "threshold": float(params.get("threshold", 0.5)),
                "temperature": temperature,
                "pair_probability_sum": float(matrix.sum()),
            },
        )
        self._export_data = {
            "n_residues": int(len(unpaired)),
            "mfe_energy_kcal": energy,
            "mean_unpaired": float(unpaired.mean()),
            "max_unpaired": float(unpaired.max()),
            "n_accessible_segments": len(segments),
            "temperature": temperature,
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
