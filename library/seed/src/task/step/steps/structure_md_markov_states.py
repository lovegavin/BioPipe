"""structure_md_markov_states: Markov state model from conformational clustering."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_conformational_clusters import cluster_frames, pairwise_rmsd
from src.task.step.steps.structure_md_pca import ca_indices, kabsch, load_frames


def transition_counts(labels: np.ndarray, n_states: int, lag: int = 1) -> np.ndarray:
    """Count transitions between states separated by a lag of frames."""

    labels = np.asarray(labels, dtype=int)
    if lag < 1:
        raise StepError("structure_md_markov_states: lag must be at least 1")
    if lag >= len(labels):
        raise StepError("structure_md_markov_states: lag must be smaller than the frame count")
    counts = np.zeros((n_states, n_states), dtype=float)
    for start in range(len(labels) - lag):
        counts[labels[start] - 1, labels[start + lag] - 1] += 1.0
    return counts


def transition_matrix(counts: np.ndarray, *, pseudo: float = 0.0) -> np.ndarray:
    """Row-normalise a count matrix into a row-stochastic transition matrix."""

    if pseudo < 0:
        raise StepError("structure_md_markov_states: pseudo count must be non-negative")
    counts = np.asarray(counts, dtype=float) + pseudo
    totals = counts.sum(axis=1)
    matrix = np.zeros_like(counts)
    for index, total in enumerate(totals):
        if total > 0:
            matrix[index] = counts[index] / total
        else:
            matrix[index, index] = 1.0
    return matrix


def implied_timescales(matrix: np.ndarray, lag_frames: int, frame_time_ps: float, n: int = 3) -> list[float]:
    """Return the slowest implied timescales in picoseconds."""

    values = np.linalg.eigvals(matrix)
    values = np.sort(np.real(values))[::-1]
    timescales = []
    for value in values[1 : n + 1]:
        if 0.0 < value < 1.0:
            timescales.append(float(-lag_frames * frame_time_ps / np.log(value)))
    return timescales


class StructureMdMarkovStatesStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_markov_states.StructureMdMarkovStatesStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_markov_states",
        "version": "1.0.0",
        "kind": "operator",
        "title": "马尔可夫状态模型",
        "description": (
            "Cluster trajectory frames by CA RMSD, estimate a transition matrix at a "
            "chosen lag with pseudo counts, and report state populations, dwell times "
            "and implied timescales."
        ),
        "category": "Structure",
        "icon": "GridNine",
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
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_markov_states")
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1], "structure_md_markov_states")
        selected = kabsch(frames[:, indices, :])
        matrix = pairwise_rmsd(selected)
        labels, n_clusters = cluster_frames(matrix, float(params.get("cutoff", 1.5)))
        limit = int(params.get("max_states", 8))
        if n_clusters > limit:
            raise StepError(
                f"structure_md_markov_states: {n_clusters} clusters exceed max_states {limit}; "
                "increase the cutoff or max_states"
            )
        lag = int(params.get("lag_frames", 1))
        counts = transition_counts(labels, n_clusters, lag)
        transition = transition_matrix(counts, pseudo=float(params.get("pseudo_count", 0.0)))
        frame_time_ps = float(params.get("frame_time_ps", 0.2))
        if frame_time_ps <= 0:
            raise StepError("structure_md_markov_states: frame_time_ps must be positive")
        populations = np.bincount(labels, minlength=n_clusters + 1)[1:] / len(labels)
        rows = []
        names = {}
        for state in range(n_clusters):
            self_probability = float(transition[state, state])
            dwell = float(1.0 / max(1.0 - self_probability, 1e-9))
            names[f"state{state + 1}"] = state
            rows.append([float(populations[state]), self_probability, dwell, dwell * frame_time_ps])
        values = np.linalg.eigvals(transition)
        values = np.sort(np.real(values))[::-1]
        timescales = implied_timescales(transition, lag, frame_time_ps, 3)
        out = str(params.get("output", "states"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["state", "statistic"],
            labels={"state": names, "statistic": {"population": 0, "self_transition": 1, "dwell_frames": 2, "dwell_ps": 3}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_states": n_clusters,
                "cutoff": float(params.get("cutoff", 1.5)),
                "lag_frames": lag,
                "frame_time_ps": frame_time_ps,
                "transition_matrix": [[float(value) for value in row] for row in transition],
                "eigenvalues": [float(value) for value in values],
                "implied_timescales_ps": timescales,
                "max_pairwise_rmsd": float(matrix.max()),
                "n_transitions": int(counts.sum()),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_states": n_clusters,
            "lag_frames": lag,
            "frame_time_ps": frame_time_ps,
            "implied_timescales_ps": timescales,
            "n_transitions": int(counts.sum()),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
