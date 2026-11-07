"""structure_md_free_energy_landscape: 2D free-energy surface from PC projections."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_pca import ca_indices, covariance, kabsch, load_frames, pca_modes

K_B_KJ = 0.008314462618


def project(frames: np.ndarray, matrix: np.ndarray, modes: tuple[int, int] = (0, 1), n_modes: int = 10) -> np.ndarray:
    """Project aligned frames onto two principal components."""

    flattened = frames.reshape(len(frames), -1)
    centered = flattened - flattened.mean(axis=0)
    values, vectors = np.linalg.eigh(matrix)
    order = np.argsort(values)[::-1]
    vectors = vectors[:, order][:, modes]
    return centered @ vectors


def free_energy(pc: np.ndarray, *, bins: int = 20, temperature: float = 300.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a 2D histogram and the corresponding free-energy surface in kJ/mol."""

    counts, x_edges, y_edges = np.histogram2d(pc[:, 0], pc[:, 1], bins=bins)
    total = counts.sum()
    if total == 0:
        raise StepError("structure_md_free_energy_landscape: the projection holds no sample")
    probability = counts / total
    occupied = probability > 0
    energy = np.full_like(probability, np.nan)
    energy[occupied] = -K_B_KJ * temperature * np.log(probability[occupied] / probability[occupied].max())
    return counts, probability, energy


class StructureMdFreeEnergyLandscapeStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_free_energy_landscape.StructureMdFreeEnergyLandscapeStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_free_energy_landscape",
        "version": "1.0.0",
        "kind": "operator",
        "title": "自由能景观",
        "description": (
            "Project trajectory frames onto the two leading principal components and "
            "build a histogram-based free-energy landscape F = -kT ln p."
        ),
        "category": "Structure",
        "icon": "ChartScatter",
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
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_free_energy_landscape")
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1], "structure_md_free_energy_landscape")
        aligned = kabsch(frames[:, indices, :])
        matrix = covariance(aligned)
        pc1 = int(params.get("pc1", 0))
        pc2 = int(params.get("pc2", 1))
        if pc1 == pc2 or min(pc1, pc2) < 0:
            raise StepError("structure_md_free_energy_landscape: pc1 and pc2 must be distinct non-negative indices")
        temperature = float(params.get("temperature", 300.0))
        if temperature <= 0:
            raise StepError("structure_md_free_energy_landscape: temperature must be positive")
        bins = int(params.get("bins", 20))
        if bins < 2:
            raise StepError("structure_md_free_energy_landscape: bins must be at least 2")
        pc = project(aligned, matrix, (pc1, pc2))
        counts, probability, energy = free_energy(pc, bins=bins, temperature=temperature)
        x_centers = (np.arange(bins) + 0.5)
        rows = []
        labels = {}
        for i in range(bins):
            for j in range(bins):
                if not np.isfinite(energy[i, j]):
                    continue
                rows.append([float(x_centers[i]), float(x_centers[j]), float(probability[i, j]), float(energy[i, j])])
                labels[f"c{i}:{j}"] = len(rows) - 1
        out = str(params.get("output", "landscape"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["cell", "statistic"],
            labels={"cell": labels, "statistic": {"pc1_bin": 0, "pc2_bin": 1, "probability": 2, "free_energy_kj": 3}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_occupied": len(rows),
                "bins": bins,
                "temperature": temperature,
                "pc1": pc1,
                "pc2": pc2,
                "min_free_energy_kj": float(np.nanmin(energy)),
                "max_free_energy_kj": float(np.nanmax(energy)),
                "probability_sum": float(probability.sum()),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_occupied": len(rows),
            "bins": bins,
            "temperature": temperature,
            "min_free_energy_kj": float(np.nanmin(energy)),
            "max_free_energy_kj": float(np.nanmax(energy)),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
