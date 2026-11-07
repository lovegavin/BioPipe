"""structure_md_pca: essential dynamics from a trajectory."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step

TOL = 1e-10


def load_frames(path: Path | str, operator: str = "structure_md_pca") -> np.ndarray:
    path = Path(path).expanduser()
    if not path.is_file():
        raise StepError(f"{operator}: trajectory_path {path} is not a file")
    frames = np.load(path)
    if frames.ndim != 3 or frames.shape[2] != 3:
        raise StepError(f"{operator}: trajectory must have shape (frames, atoms, 3)")
    if frames.shape[0] < 2:
        raise StepError(f"{operator}: at least two frames are required")
    return np.asarray(frames, dtype=float) * 10.0


def ca_indices(topology: Path | str, atom_count: int, operator: str = "structure_md_pca") -> np.ndarray:
    topology = Path(topology).expanduser()
    if not topology.is_file():
        raise StepError(f"{operator}: topology_path {topology} is not a file")
    indices = []
    for index, line in enumerate(topology.read_text().splitlines()):
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            indices.append(index)
    if not indices:
        raise StepError(f"{operator}: the topology file carries no CA atom")
    if max(indices) >= atom_count:
        raise StepError(f"{operator}: the trajectory has {atom_count} atoms but the topology indexes atom {max(indices)}")
    return np.asarray(indices, dtype=int)


def kabsch(frames: np.ndarray) -> np.ndarray:
    """Superpose every frame onto the first one."""

    reference = frames[0]
    reference_center = reference.mean(axis=0)
    centered_reference = reference - reference_center
    aligned = np.empty_like(frames)
    aligned[0] = centered_reference
    for index in range(1, len(frames)):
        mobile = frames[index]
        center = mobile.mean(axis=0)
        centered = mobile - center
        covariance = centered.T @ centered_reference
        u, _, vt = np.linalg.svd(covariance)
        rotation = u @ vt
        if np.linalg.det(rotation) < 0:
            u[:, -1] *= -1
            rotation = u @ vt
        aligned[index] = centered @ rotation
    return aligned


def covariance(aligned: np.ndarray) -> np.ndarray:
    flattened = aligned.reshape(len(aligned), -1)
    deviations = flattened - flattened.mean(axis=0)
    return deviations.T @ deviations / max(len(flattened) - 1, 1)


def pca_modes(matrix: np.ndarray, n_modes: int) -> tuple[np.ndarray, np.ndarray]:
    values, _ = np.linalg.eigh(matrix)
    order = np.argsort(values)[::-1]
    values = values[order]
    values = values[values > TOL]
    if values.size == 0:
        raise StepError("structure_md_pca: the covariance matrix has no non-zero mode")
    n_modes = min(int(n_modes), len(values))
    total = float(values.sum())
    fractions = values[:n_modes] / total
    return values[:n_modes], fractions


class StructureMdPcaStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_pca.StructureMdPcaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_pca",
        "version": "1.0.0",
        "kind": "operator",
        "title": "轨迹主成分分析",
        "description": (
            "Superpose trajectory frames on CA atoms, build the coordinate covariance "
            "matrix and report essential-dynamics modes with variance fractions."
        ),
        "category": "Structure",
        "icon": "ChartLine",
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
        frames = load_frames(str(params.get("trajectory_path", "")))
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1])
        selected = frames[:, indices, :]
        aligned = kabsch(selected)
        matrix = covariance(aligned)
        values, fractions = pca_modes(matrix, int(params.get("n_modes", 10)))
        from src.core.forms import Form

        rows = np.vstack([values, fractions, np.cumsum(fractions)]).T.astype(np.float32)
        out = str(params.get("output", "modes"))
        ctx[out] = Form(
            data=rows,
            dims=["mode", "statistic"],
            labels={"mode": {f"mode{index + 1}": index for index in range(len(values))}, "statistic": {"eigenvalue": 0, "variance_fraction": 1, "cumulative_fraction": 2}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_atoms": int(len(indices)),
                "n_dimensions": int(matrix.shape[0]),
                "total_variance": float(np.linalg.eigvalsh(matrix)[-1]) if matrix.size else 0.0,
                "variance_sum": float(np.trace(matrix)),
                "n_modes": int(len(values)),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_atoms": int(len(indices)),
            "n_modes": int(len(values)),
            "top_eigenvalue": float(values[0]),
            "top_fraction": float(fractions[0]),
            "variance_sum": float(np.trace(matrix)),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
