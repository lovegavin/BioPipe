"""structure_md_quasiharmonic_entropy: configurational entropy of a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_pca import ca_indices, covariance, kabsch, load_frames

TOL = 1e-10
K_B = 1.380649e-23
R_GAS = 8.314462618


def entropy_from_covariance(matrix: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    """Return total entropy in units of k_B, per-mode contributions and eigenvalues."""

    values = np.linalg.eigvalsh(matrix)
    values = values[values > TOL]
    if values.size == 0:
        raise StepError("structure_md_quasiharmonic_entropy: the covariance matrix has no non-zero mode")
    contributions = 0.5 * (1.0 + np.log(2.0 * np.pi * values))
    return float(contributions.sum()), contributions, values


class StructureMdQuasiharmonicEntropyStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_quasiharmonic_entropy.StructureMdQuasiharmonicEntropyStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_quasiharmonic_entropy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "准谐振熵",
        "description": (
            "Estimate configurational entropy from the quasiharmonic covariance matrix of a "
            "trajectory (Schlitter formula), with per-mode contributions."
        ),
        "category": "Structure",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_quasiharmonic_entropy")
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1], "structure_md_quasiharmonic_entropy")
        aligned = kabsch(frames[:, indices, :])
        matrix = covariance(aligned)
        total, contributions, values = entropy_from_covariance(matrix)
        top = int(params.get("n_modes", 10))
        order = np.argsort(contributions)[::-1][:top]
        rows = []
        labels = {}
        for rank, index in enumerate(order):
            rows.append([values[index], contributions[index], contributions[index] / total])
            labels[f"mode{rank + 1}"] = rank
        rows.append([float(values.sum()), total, 1.0])
        labels["total"] = len(rows) - 1
        out = str(params.get("output", "entropy"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["mode", "statistic"],
            labels={"mode": labels, "statistic": {"eigenvalue": 0, "entropy_kb": 1, "fraction": 2}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_atoms": int(len(indices)),
                "n_modes": int(len(values)),
                "total_entropy_kb": total,
                "entropy_kj_mol_k": total * R_GAS / 1000.0,
                "entropy_per_dof_kb": total / len(values),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_atoms": int(len(indices)),
            "n_modes": int(len(values)),
            "total_entropy_kb": total,
            "entropy_kj_mol_k": total * R_GAS / 1000.0,
            "entropy_per_dof_kb": total / len(values),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
