"""structure_gnm_flexibility: Gaussian network model fluctuation profile."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, residue_labels

_IGNORE = 1e-8


def ca_atoms(form, atom_dim: str, field_dim: str, chain: str = "") -> tuple[list[str], np.ndarray]:
    """Return one CA coordinate per residue, ordered by chain and residue number."""

    if form.data.size == 0:
        raise StepError("structure_gnm_flexibility: the structure form is empty")
    names = decode_column(form, field_dim, "atom_name")
    chains = decode_column(form, field_dim, "chain")
    labels = residue_labels(form, field_dim)
    numbers = [int(str(label).split(":")[-1]) if str(label).split(":")[-1].isdigit() else 0 for label in labels]
    wanted = chain.strip()
    selected: dict[str, tuple[int, int]] = {}
    coordinates: dict[str, np.ndarray] = {}
    x = form.data[:, form.labels[field_dim]["x"]]
    y = form.data[:, form.labels[field_dim]["y"]]
    z = form.data[:, form.labels[field_dim]["z"]]
    for index in range(len(names)):
        if names[index] != "CA":
            continue
        if wanted and chains[index] != wanted:
            continue
        label = labels[index]
        if label in coordinates:
            continue
        selected[label] = (chains[index], numbers[index])
        coordinates[label] = np.array([x[index], y[index], z[index]], dtype=float)
    if len(coordinates) < 3:
        raise StepError("structure_gnm_flexibility: at least three CA atoms are required")
    order = sorted(coordinates, key=lambda key: (selected[key][0], selected[key][1], key))
    return order, np.vstack([coordinates[key] for key in order])


def kirchhoff(coordinates: np.ndarray, gamma: float = 1.0, cutoff: float = 10.0) -> np.ndarray:
    """Build the Kirchhoff matrix with a distance cutoff."""

    if cutoff <= 0:
        raise StepError("structure_gnm_flexibility: cutoff must be positive")
    diff = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    matrix = np.zeros((len(coordinates), len(coordinates)), dtype=float)
    mask = (distances <= cutoff) & (~np.eye(len(coordinates), dtype=bool))
    matrix[mask] = -1.0
    matrix[np.diag_indices_from(matrix)] = -matrix.sum(axis=1)
    return gamma * matrix


def gnm_msf(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Return per-residue mean-square fluctuations, mode-1 weights and collectivity."""

    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    keep = eigenvalues > _IGNORE
    values = eigenvalues[keep]
    vectors = eigenvectors[:, keep]
    msf = (vectors ** 2) @ (1.0 / values)
    first = vectors[:, 0] ** 2
    first = first / first.sum()
    entropy = -float(np.sum(first * np.log(first + 1e-300)))
    collectivity = float(np.exp(entropy) / len(first))
    return msf, first, collectivity


class StructureGnmFlexibilityStep(Step):
    provider = "operon-core"
    parameters_file = "structure_gnm_flexibility.StructureGnmFlexibilityStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_gnm_flexibility",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GNM 柔性分析",
        "description": (
            "Build a Gaussian network model from CA atoms and report per-residue "
            "mean-square fluctuations, the slowest mode weights and its collectivity."
        ),
        "category": "Structure",
        "icon": "Waves",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "atom_dim"}, {"param": "field_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        labels, coordinates = ca_atoms(inputs[0], str(params.get("atom_dim", "atom")), str(params.get("field_dim", "field")), str(params.get("chain", "")))
        matrix = kirchhoff(coordinates, float(params.get("gamma", 1.0)), float(params.get("cutoff", 10.0)))
        msf, first, collectivity = gnm_msf(matrix)
        mean = float(msf.mean())
        if not np.isfinite(mean) or mean <= 0:
            raise StepError("structure_gnm_flexibility: the Kirchhoff matrix has no non-zero mode")
        from src.core.forms import Form

        rows = np.vstack([msf, msf / mean, first]).T.astype(np.float32)
        out = str(params.get("output", "flexibility"))
        ctx[out] = Form(
            data=rows,
            dims=[str(params.get("residue_dim", "residue")), "statistic"],
            labels={str(params.get("residue_dim", "residue")): {label: index for index, label in enumerate(labels)}, "statistic": {name: index for index, name in enumerate(("msf", "norm_msf", "mode1_weight"))}},
            info={
                "n_residues": len(labels),
                "zero_modes": int(np.sum(np.linalg.eigvalsh(matrix) <= _IGNORE)),
                "msf_min": float(msf.min()),
                "msf_max": float(msf.max()),
                "collectivity": collectivity,
                "cutoff": float(params.get("cutoff", 10.0)),
                "gamma": float(params.get("gamma", 1.0)),
                "chain": str(params.get("chain", "")),
            },
        )
        self._export_data = {
            "n_residues": len(labels),
            "zero_modes": int(np.sum(np.linalg.eigvalsh(matrix) <= _IGNORE)),
            "msf_min": float(msf.min()),
            "msf_max": float(msf.max()),
            "collectivity": collectivity,
            "cutoff": float(params.get("cutoff", 10.0)),
            "gamma": float(params.get("gamma", 1.0)),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
