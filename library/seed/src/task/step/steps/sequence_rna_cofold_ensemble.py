"""sequence_rna_cofold_ensemble: two-strand ensemble pairing statistics."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_ALPHABET = set("ACGUN")


def cofold_ensemble(sequence_a: str, sequence_b: str, temperature: float = 37.0) -> dict:
    """Return pair probabilities of the A&B duplex ensemble."""

    left = sequence_a.strip().upper().replace("T", "U")
    right = sequence_b.strip().upper().replace("T", "U")
    if not left or not right:
        raise StepError("sequence_rna_cofold_ensemble: both strands must be non-empty")
    invalid = sorted((set(left) | set(right)) - _ALPHABET)
    if invalid:
        raise StepError(f"sequence_rna_cofold_ensemble: non-RNA residue(s) {invalid}")
    try:
        import RNA
    except ImportError:
        raise StepError(
            "sequence_rna_cofold_ensemble: the ViennaRNA Python bindings are required; "
            "install them with 'python -m pip install ViennaRNA'"
        ) from None
    parameters = RNA.md()
    parameters.temperature = float(temperature)
    compound = RNA.fold_compound(f"{left}&{right}", parameters)
    compound.pf()
    structure, energy = compound.mfe()
    matrix = np.asarray(compound.bpp(), dtype=float)
    if matrix.shape[0] == len(left) + len(right) + 1:
        matrix = matrix[1:, 1:]
    matrix = matrix + matrix.T
    return {"left": left, "right": right, "structure": str(structure), "energy": float(energy), "matrix": matrix}


def per_base_statistics(matrix: np.ndarray, n_left: int, n_right: int) -> dict:
    """Split pairing probabilities into intra-strand, inter-strand and unpaired parts."""

    total = n_left + n_right
    if matrix.shape != (total, total):
        raise StepError("sequence_rna_cofold_ensemble: unexpected pair-probability shape")
    inter = np.zeros(total)
    intra = np.zeros(total)
    for i in range(total):
        for j in range(total):
            if i == j or matrix[i, j] == 0.0:
                continue
            if (i < n_left) != (j < n_left):
                inter[i] += matrix[i, j]
            else:
                intra[i] += matrix[i, j]
    unpaired = np.clip(1.0 - inter - intra, 0.0, 1.0)
    interface = [index for index in range(total) if inter[index] >= 0.05]
    return {
        "inter": inter,
        "intra": intra,
        "unpaired": unpaired,
        "total_inter": float(inter.sum() / 2.0),
        "interface_bases": interface,
    }


class SequenceRnaCofoldEnsembleStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_rna_cofold_ensemble.SequenceRnaCofoldEnsembleStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_rna_cofold_ensemble",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 双链系综",
        "description": (
            "Run the ViennaRNA two-strand partition function and split each base's "
            "pairing probability into unpaired, intra-strand and inter-strand parts, "
            "with the MFE cofold structure and the interface bases."
        ),
        "category": "Sequence",
        "icon": "ShareNetwork",
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
        if len(sequences) != 2:
            raise StepError(f"sequence_rna_cofold_ensemble: expected exactly two strands, got {len(sequences)}")
        temperature = float(params.get("temperature", 37.0))
        if not 0.0 < temperature <= 100.0:
            raise StepError("sequence_rna_cofold_ensemble: temperature must be in (0, 100]")
        result = cofold_ensemble(sequences[0], sequences[1], temperature)
        n_left = len(result["left"])
        n_right = len(result["right"])
        stats = per_base_statistics(result["matrix"], n_left, n_right)
        rows = []
        labels = {}
        for index in range(n_left + n_right):
            strand = "A" if index < n_left else "B"
            position = index + 1 if index < n_left else index - n_left + 1
            labels[f"{strand}:{position}"] = index
            rows.append([stats["unpaired"][index], stats["intra"][index], stats["inter"][index]])
        out = str(params.get("output", "cofold"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["base", "statistic"],
            labels={"base": labels, "statistic": {"unpaired_probability": 0, "intra_probability": 1, "inter_probability": 2}},
            info={
                "n_left": n_left,
                "n_right": n_right,
                "sequence_a": result["left"],
                "sequence_b": result["right"],
                "mfe_energy_kcal": result["energy"],
                "mfe_structure": result["structure"],
                "total_interstrand_probability": stats["total_inter"],
                "n_interface_bases": len(stats["interface_bases"]),
                "interface_bases": [("A" if index < n_left else "B") + ":" + str(index + 1 if index < n_left else index - n_left + 1) for index in stats["interface_bases"]],
                "temperature": temperature,
            },
        )
        self._export_data = {
            "n_left": n_left,
            "n_right": n_right,
            "mfe_energy_kcal": result["energy"],
            "total_interstrand_probability": stats["total_inter"],
            "n_interface_bases": len(stats["interface_bases"]),
            "temperature": temperature,
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
