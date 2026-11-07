"""structure_md_communication_path: allosteric paths from a dynamic cross-correlation matrix."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import dijkstra

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_pca import ca_indices, covariance, kabsch, load_frames

EPS = 1e-3


def dccm(matrix: np.ndarray) -> np.ndarray:
    """Normalised dynamic cross-correlation matrix from a covariance matrix."""

    diagonal = np.sqrt(np.clip(np.diag(matrix), EPS, None))
    correlation = matrix / np.outer(diagonal, diagonal)
    return np.clip(correlation, -1.0, 1.0)


def path_weights(correlation: np.ndarray, min_correlation: float = 0.05) -> np.ndarray:
    """Convert a residue cross-correlation matrix into positive edge weights."""

    if min_correlation < 0 or min_correlation >= 1:
        raise StepError("structure_md_communication_path: min_correlation must be in [0, 1)")
    strength = np.abs(correlation) * (np.abs(correlation) >= min_correlation)
    weights = -np.log(np.clip(strength, EPS, 1.0))
    np.fill_diagonal(weights, 0.0)
    return weights


def shortest_path(weights: np.ndarray, source: int, target: int) -> tuple[list[int], float]:
    """Dijkstra shortest path on a dense weight matrix (entry i, i+1 = residue i)."""

    count = len(weights)
    if not 0 <= source < count or not 0 <= target < count:
        raise StepError("structure_md_communication_path: source and target must be residue indices")
    if source == target:
        raise StepError("structure_md_communication_path: source and target must differ")
    unvisited = np.ones(count, dtype=bool)
    distance = np.full(count, np.inf)
    previous = np.full(count, -1, dtype=int)
    distance[source] = 0.0
    while unvisited.any():
        candidates = np.where(unvisited, distance, np.inf)
        current = int(np.argmin(candidates))
        if not np.isfinite(candidates[current]):
            break
        unvisited[current] = False
        if current == target:
            break
        updates = distance[current] + weights[current]
        better = unvisited & (updates < distance)
        distance[better] = updates[better]
        previous[better] = current
    if not np.isfinite(distance[target]):
        raise StepError("structure_md_communication_path: no path connects the residues at this correlation cutoff")
    path = [target]
    while path[-1] != source:
        path.append(int(previous[path[-1]]))
    path.reverse()
    return path, float(distance[target])


class StructureMdCommunicationPathStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_communication_path.StructureMdCommunicationPathStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_communication_path",
        "version": "1.0.0",
        "kind": "operator",
        "title": "动态通讯路径",
        "description": (
            "Build a dynamic cross-correlation matrix from a trajectory and extract "
            "the shortest allosteric communication path between two residues."
        ),
        "category": "Structure",
        "icon": "ShareNetwork",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": ["scipy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_communication_path")
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1], "structure_md_communication_path")
        aligned = kabsch(frames[:, indices, :])
        matrix = covariance(aligned)
        correlation = dccm(matrix)
        weights = path_weights(correlation, float(params.get("min_correlation", 0.05)))
        source = int(params.get("source", 1)) - 1
        target = int(params.get("target", 2)) - 1
        count = len(indices)
        if not 0 <= source < count or not 0 <= target < count:
            raise StepError(f"structure_md_communication_path: source and target must be between 1 and {count}")
        path, length = shortest_path(weights, source, target)
        scipy_distance = dijkstra(weights, directed=False, indices=source)[target]
        rows = []
        labels = {}
        for step, node in enumerate(path):
            rows.append([float(node + 1), float(weights[path[step - 1], node] if step else 0.0), float(sum(weights[path[k - 1], path[k]] for k in range(1, step + 1)))])
            labels[f"step{step + 1}"] = step
        out = str(params.get("output", "path"))
        ctx[out] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["step", "statistic"],
            labels={"step": labels, "statistic": {"residue": 0, "edge_weight": 1, "cumulative_weight": 2}},
            info={
                "n_steps": len(path),
                "path_length": length,
                "path_residues": [node + 1 for node in path],
                "source": source + 1,
                "target": target + 1,
                "n_atoms": int(count),
                "min_correlation": float(params.get("min_correlation", 0.05)),
                "scipy_distance": float(scipy_distance),
            },
        )
        self._export_data = {
            "n_steps": len(path),
            "path_length": length,
            "path_residues": [node + 1 for node in path],
            "source": source + 1,
            "target": target + 1,
            "n_atoms": int(count),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
