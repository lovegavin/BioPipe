"""structure_md_conformational_clusters: average-linkage clustering of frames by RMSD."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps.structure_md_pca import ca_indices, kabsch, load_frames


def pairwise_rmsd(frames: np.ndarray) -> np.ndarray:
    """Return the symmetric pairwise CA RMSD matrix after global superposition."""

    flattened = frames - frames.mean(axis=1, keepdims=True)
    count = len(flattened)
    matrix = np.zeros((count, count))
    for i in range(count):
        for j in range(i + 1, count):
            a = flattened[i]
            b = flattened[j]
            covariance = a.T @ b
            u, _, vt = np.linalg.svd(covariance)
            rotation = u @ vt
            if np.linalg.det(rotation) < 0:
                u[:, -1] *= -1
                rotation = u @ vt
            rotated = a @ rotation
            value = float(np.sqrt(((rotated - b) ** 2).sum(axis=1).mean()))
            matrix[i, j] = matrix[j, i] = value
    return matrix


def cluster_frames(matrix: np.ndarray, cutoff: float) -> tuple[np.ndarray, int]:
    """Average-linkage clustering with an RMSD cutoff."""

    if cutoff <= 0:
        raise StepError("structure_md_conformational_clusters: cutoff must be positive")
    condensed = squareform(matrix, checks=False)
    tree = linkage(condensed, method="average")
    labels = fcluster(tree, t=cutoff, criterion="distance")
    return labels, int(labels.max())


class StructureMdConformationalClustersStep(Step):
    provider = "operon-core"
    parameters_file = "structure_md_conformational_clusters.StructureMdConformationalClustersStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_md_conformational_clusters",
        "version": "1.0.0",
        "kind": "operator",
        "title": "构象聚类",
        "description": (
            "Cluster trajectory frames by pairwise CA RMSD with average linkage and a "
            "distance cutoff; report cluster membership and distance to cluster centre."
        ),
        "category": "Structure",
        "icon": "CirclesThree",
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
        frames = load_frames(str(params.get("trajectory_path", "")), "structure_md_conformational_clusters")
        indices = ca_indices(Path(str(params.get("topology_path", ""))), frames.shape[1], "structure_md_conformational_clusters")
        selected = kabsch(frames[:, indices, :])
        matrix = pairwise_rmsd(selected)
        cutoff = float(params.get("cutoff", 1.5))
        labels, n_clusters = cluster_frames(matrix, cutoff)
        sizes = [int(np.sum(labels == label)) for label in range(1, n_clusters + 1)]
        representatives = [int(np.argmin(np.where(labels == label, matrix.sum(axis=1), np.inf))) for label in range(1, n_clusters + 1)]
        distances = []
        for frame, label in enumerate(labels):
            same = np.where(labels == label)[0]
            distances.append(float(matrix[frame, same].mean()))
        from src.core.forms import Form

        rows = np.vstack([labels.astype(float), np.asarray(distances)]).T.astype(np.float32)
        out = str(params.get("output", "clusters"))
        ctx[out] = Form(
            data=rows,
            dims=["frame", "statistic"],
            labels={"frame": {f"frame{index + 1}": index for index in range(len(labels))}, "statistic": {"cluster": 0, "mean_distance": 1}},
            info={
                "n_frames": int(frames.shape[0]),
                "n_clusters": n_clusters,
                "cluster_sizes": sizes,
                "representatives": representatives,
                "cutoff": cutoff,
                "max_pairwise_rmsd": float(matrix.max()),
            },
        )
        self._export_data = {
            "n_frames": int(frames.shape[0]),
            "n_clusters": n_clusters,
            "cluster_sizes": sizes,
            "representatives": representatives,
            "cutoff": cutoff,
            "max_pairwise_rmsd": float(matrix.max()),
        }

    def export(self, ctx):
        return getattr(self, "_export_data", {})
