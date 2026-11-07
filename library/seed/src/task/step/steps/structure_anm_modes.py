"""structure_anm_modes: anisotropic network model fluctuation profile."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column, residue_labels

_IGNORE = 1e-8


def ca_atoms(form, atom_dim: str, field_dim: str, chain: str = "") -> tuple[list[str], np.ndarray]:
    """Return one CA coordinate per residue, ordered by chain and residue number."""

    if form.data.size == 0:
        raise StepError("structure_anm_modes: the structure form is empty")
    names = decode_column(form, field_dim, "atom_name")
    chains = decode_column(form, field_dim, "chain")
    labels = residue_labels(form, field_dim)
    wanted = chain.strip()
    coordinates: dict[str, np.ndarray] = {}
    keys: dict[str, tuple[str, int]] = {}
    for index in range(len(names)):
        if names[index] != "CA" or (wanted and chains[index] != wanted):
            continue
        label = labels[index]
        if label in coordinates:
            continue
        tail = str(label).split(":")[-1]
        coordinates[label] = np.array([form.data[index, form.labels[field_dim][axis]] for axis in ("x", "y", "z")], dtype=float)
        keys[label] = (chains[index], int(tail) if tail.isdigit() else 0)
    if len(coordinates) < 3:
        raise StepError("structure_anm_modes: at least three CA atoms are required")
    order = sorted(coordinates, key=lambda key: (keys[key][0], keys[key][1], key))
    return order, np.vstack([coordinates[key] for key in order])


def anm_hessian(coordinates: np.ndarray, cutoff: float = 15.0, gamma: float = 1.0) -> np.ndarray:
    """Build the 3N x 3N anisotropic network model Hessian."""

    if cutoff <= 0:
        raise StepError("structure_anm_modes: cutoff must be positive")
    count = len(coordinates)
    hessian = np.zeros((count * 3, count * 3), dtype=float)
    for i in range(count):
        for j in range(i + 1, count):
            vector = coordinates[j] - coordinates[i]
            distance = float(np.linalg.norm(vector))
            if distance <= 0 or distance > cutoff:
                continue
            unit = vector / distance
            block = gamma * np.outer(unit, unit)
            hessian[i * 3:(i + 1) * 3, i * 3:(i + 1) * 3] += block
            hessian[j * 3:(j + 1) * 3, j * 3:(j + 1) * 3] += block
            hessian[i * 3:(i + 1) * 3, j * 3:(j + 1) * 3] -= block
            hessian[j * 3:(j + 1) * 3, i * 3:(i + 1) * 3] -= block
    return hessian


def anm_msf(hessian: np.ndarray, n_modes: int = 20) -> tuple[np.ndarray, np.ndarray, float]:
    """Return per-residue MSF, the slowest eigenvalues and mode-1 collectivity."""

    eigenvalues, eigenvectors = np.linalg.eigh(hessian)
    keep = eigenvalues > _IGNORE
    values = eigenvalues[keep][:n_modes]
    vectors = eigenvectors[:, keep][:, :n_modes]
    msf = (vectors ** 2) @ (1.0 / values)
    residue_msf = msf.reshape(-1, 3).sum(axis=1)
    first = vectors[:, 0] ** 2
    first = first / first.sum()
    entropy = -float(np.sum(first * np.log(first + 1e-300)))
    collectivity = float(np.exp(entropy) / len(first))
    return residue_msf, eigenvalues[keep][:10], collectivity


class StructureAnmModesStep(Step):
    provider = "operon-core"
    parameters_file = "structure_anm_modes.StructureAnmModesStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_anm_modes",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ANM 模式分析",
        "description": (
            "Build an anisotropic network model Hessian from CA atoms and report "
            "per-residue mean-square fluctuations, slowest eigenvalues and collectivity."
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
        hessian = anm_hessian(coordinates, float(params.get("cutoff", 15.0)), float(params.get("gamma", 1.0)))
        modes = int(params.get("n_modes", 20))
        if modes < 1:
            raise StepError("structure_anm_modes: n_modes must be at least 1")
        msf, slowest, collectivity = anm_msf(hessian, modes)
        mean = float(msf.mean())
        if not np.isfinite(mean) or mean <= 0:
            raise StepError("structure_anm_modes: the Hessian has no non-zero mode")
        from src.core.forms import Form

        rows = np.vstack([msf, msf / mean]).T.astype(np.float32)
        out = str(params.get("output", "modes"))
        ctx[out] = Form(
            data=rows,
            dims=[str(params.get("residue_dim", "residue")), "statistic"],
            labels={str(params.get("residue_dim", "residue")): {label: index for index, label in enumerate(labels)}, "statistic": {"msf": 0, "norm_msf": 1}},
            info={
                "n_residues": len(labels),
                "n_modes": modes,
                "zero_modes": int(np.sum(np.linalg.eigvalsh(hessian) <= _IGNORE)),
                "slowest_eigenvalues": [float(value) for value in slowest],
                "collectivity": collectivity,
                "msf_min": float(msf.min()),
                "msf_max": float(msf.max()),
                "cutoff": float(params.get("cutoff", 15.0)),
                "gamma": float(params.get("gamma", 1.0)),
            },
        )
        self._export_data = {
            "n_residues": len(labels),
            "n_modes": modes,
            "zero_modes": int(np.sum(np.linalg.eigvalsh(hessian) <= _IGNORE)),
            "collectivity": collectivity,
            "msf_min": float(msf.min()),
            "msf_max": float(msf.max()),
            "cutoff": float(params.get("cutoff", 15.0)),
            "slowest_eigenvalues": [float(value) for value in slowest],
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
