"""Cluster ProteinMPNN designs by pairwise sequence identity."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from .proteinmpnn_design_diversity import (
    MODELS,
    cluster_ids,
    pairwise_identities,
    run_designer,
)


def cluster_rows(identities: np.ndarray, clusters: list[int]) -> list[list[float]]:
    """Return [cluster, size, mean_identity, max_identity] per design."""
    rows: list[list[float]] = []
    for index, cluster in enumerate(clusters):
        members = [other for other, value in enumerate(clusters) if value == cluster]
        if len(members) <= 1:
            mean_identity = 1.0
            max_identity = 1.0
        else:
            values = [float(identities[index, other]) for other in members if other != index]
            mean_identity = float(np.mean(values))
            max_identity = float(np.max(values))
        rows.append([float(cluster + 1), float(len(members)), mean_identity, max_identity])
    return rows


def consensus_sequence(sequences: list[str], members: list[int]) -> str:
    """Most frequent residue at every position inside a cluster."""
    letters: list[str] = []
    for position in range(len(sequences[0])):
        counts: dict[str, int] = {}
        for index in members:
            letter = sequences[index][position]
            counts[letter] = counts.get(letter, 0) + 1
        letters.append(max(sorted(counts), key=lambda letter: counts[letter]))
    return "".join(letters)


class ProteinmpnnDesignClusterStep(Step):
    provider = "operon-core"
    parameters_file = "proteinmpnn_design_cluster.ProteinmpnnDesignClusterStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "proteinmpnn_design_cluster",
        "kind": "operator",
        "title": "Cluster ProteinMPNN designs",
        "description": "Sample designs with the official ProteinMPNN runner, compute pairwise sequence identity and group the designs into single-linkage clusters.",
        "category": "Machine Learning",
        "icon": "Stack",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": True},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    _STATISTICS = ("cluster", "cluster_size", "mean_identity", "max_identity")

    def run(self, ctx, inputs) -> None:
        if inputs:
            raise StepError("proteinmpnn_design_cluster: this operator takes no graph inputs")
        structure_text = str(ctx.step_params.get("structure_path") or "").strip()
        if not structure_text:
            raise StepError("proteinmpnn_design_cluster: structure_path is required")
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(f"proteinmpnn_design_cluster: structure_path {structure} does not exist")

        cluster_dim = str(ctx.step_params.get("cluster_dim", "design") or "design")
        out_name = ctx.step_params.get("output", "design_clusters") or "design_clusters"
        threshold = ctx.step_params.get("identity_threshold", 0.8)
        model_name = str(ctx.step_params.get("model_name") or "v_48_020")
        chain = str(ctx.step_params.get("chain") or "")

        if not isinstance(threshold, (int, float)) or not 0.0 < float(threshold) <= 1.0:
            raise StepError("proteinmpnn_design_cluster: identity_threshold must be in (0, 1]")
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_design_cluster: model_name must be one of {', '.join(MODELS)}"
            )

        sequences = run_designer(dict(ctx.step_params), structure, chain)
        if len(sequences) < 2:
            raise StepError("proteinmpnn_design_cluster: at least two designs are required")
        identities = pairwise_identities(sequences)
        clusters = cluster_ids(identities, float(threshold))
        rows = cluster_rows(identities, clusters)
        matrix = np.asarray(rows, dtype=np.float32)

        groups: list[list[int]] = []
        for cluster in sorted(set(clusters)):
            groups.append([index for index, value in enumerate(clusters) if value == cluster])
        consensus = [consensus_sequence(sequences, group) for group in groups]
        sizes = [len(group) for group in groups]

        labels = [f"design{index + 1}" for index in range(len(sequences))]
        out = Form(
            data=matrix,
            dims=[cluster_dim, "statistic"],
            labels={
                cluster_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(self._STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_designs": len(sequences),
                "identity_threshold": float(threshold),
                "n_clusters": len(groups),
                "cluster_sizes": sizes,
                "clusters": groups,
                "consensus_sequences": consensus,
                "sequences": sequences,
                "model_name": model_name,
                "chain": chain,
                "statistics": list(self._STATISTICS),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(sequences),
            "n_clusters": len(groups),
            "cluster_sizes": sizes,
            "identity_threshold": float(threshold),
            "consensus_sequences": consensus,
            "model_name": model_name,
        }
        print(f"[proteinmpnn_design_cluster] {len(sequences)} designs, {len(groups)} clusters")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
