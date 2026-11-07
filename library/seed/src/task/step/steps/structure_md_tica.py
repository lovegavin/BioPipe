"""structure_md_tica: time-lagged independent component analysis."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_pca import ca_indices, kabsch, load_frames

_EPS = 1e-8


def covariance_matrices(frames: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    """Return the instantaneous and time-lagged covariance matrices."""

    if lag < 1:
        raise StepError("structure_md_tica: lag must be at least 1")
    flattened = frames.reshape(len(frames), -1)
    if lag >= len(flattened):
        raise StepError("structure_md_tica: lag must be smaller than the frame count")
    mean = flattened.mean(axis=0)
    centered = flattened - mean
    count = len(centered)
    instantaneous = centered.T @ centered / max(count - 1, 1)
    lagged = centered[lag:].T @ centered[:-lag] / max(count - lag - 1, 1)
    lagged = 0.5 * (lagged + lagged.T)
    return np.atleast_2d(instantaneous), np.atleast_2d(lagged)


def tica_eigenvalues(instantaneous: np.ndarray, lagged: np.ndarray, regularization: float = 1e-6) -> np.ndarray:
    """Solve the generalised eigenvalue problem C(tau) v = lambda C(0) v."""

    values, vectors = np.linalg.eigh(instantaneous)
    floor = max(float(values.max()), _EPS) * max(float(regularization), 0.0)
    keep = values > max(_EPS, floor)
    if not np.any(keep):
        raise StepError("structure_md_tica: the instantaneous covariance matrix has no variance")
    whiten = vectors[:, keep] / np.sqrt(values[keep])
    matrix = whiten.T @ lagged @ whiten
    eigenvalues, _ = np.linalg.eigh(matrix)
    return np.sort(np.real(eigenvalues))[::-1]


def implied_timescales(eigenvalues: np.ndarray, lag: int, frame_time_ps: float, n: int = 3) -> list[float]:
    """Convert TICA eigenvalues into implied timescales in picoseconds."""

    if frame_time_ps <= 0:
        raise StepError("structure_md_tica: frame_time_ps must be positive")
    timescales = []
    for value in eigenvalues[:n]:
        if 0.0 < value < 1.0:
            timescales.append(float(-lag * frame_time_ps / np.log(value)))
    return timescales


class StructureMdTicaStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_tica.StructureMdTicaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_tica",
        "version": "1.0.0",
        "kind": "operator",
        "title": "TICA 慢成分分析",
        "description": (
            "Solve the time-lagged independent component analysis eigenproblem on "
            "superposed CA coordinates and report eigenvalues with implied timescales."
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
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_tica")
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1], "structure_md_tica")
        aligned = kabsch(frames[:, indices, :])
        flattened = aligned.reshape(len(aligned), -1)
        mean = flattened.mean(axis=0)
        _, _, vt = np.linalg.svd(flattened - mean, full_matrices=False)
        n_pca = max(1, min(int(params.get("n_pca", 10)), vt.shape[0]))
        projected = ((flattened - mean) @ vt[:n_pca].T).reshape(len(aligned), n_pca, 1)
        lag = int(params.get("lag_frames", 1))
        instantaneous, lagged = covariance_matrices(projected, lag)
        eigenvalues = tica_eigenvalues(instantaneous, lagged, float(params.get("regularization", 1e-6)))
        frame_time_ps = float(params.get("frame_time_ps", 0.2))
        timescales = implied_timescales(eigenvalues, lag, frame_time_ps, int(params.get("n_modes", 5)))
        rows = []
        names = {}
        for index, value in enumerate(eigenvalues[: int(params.get("n_modes", 5))]):
            timescale = timescales[index] if index < len(timescales) else float("nan")
            names[f"ic{index + 1}"] = index
            rows.append([float(value), float(timescale)])
        out = str(params.get("output", "components"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["mode", "statistic"],
            labels={"mode": names, "statistic": {"eigenvalue": 0, "timescale_ps": 1}},
            info={
                "n_frames": int(frames.shape[0]),
                "lag_frames": lag,
                "frame_time_ps": frame_time_ps,
                "n_features": int(instantaneous.shape[0]),
                "eigenvalues": [float(value) for value in eigenvalues[:10]],
                "implied_timescales_ps": timescales,
                "slowest_timescale_ps": timescales[0] if timescales else None,
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "lag_frames": lag,
            "frame_time_ps": frame_time_ps,
            "n_features": int(instantaneous.shape[0]),
            "slowest_timescale_ps": timescales[0] if timescales else None,
            "eigenvalues": [float(value) for value in eigenvalues[:5]],
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
