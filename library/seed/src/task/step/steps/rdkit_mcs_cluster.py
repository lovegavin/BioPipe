"""Cluster a molecule set by pairwise maximum common substructure similarity."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import (
    build_molecules,
    molecule_labels,
    parse_smiles_text,
)


def mcs_similarity(molecules: list, timeout: int = 30) -> np.ndarray:
    """Return the symmetric pairwise MCS similarity matrix (float64)."""
    from rdkit.Chem import rdFMCS

    count = len(molecules)
    matrix = np.zeros((count, count), dtype=np.float64)
    atoms = [int(molecule.GetNumHeavyAtoms()) for molecule in molecules]
    params = rdFMCS.MCSParameters()
    params.AtomCompareParameters.CompleteRingsOnly = False
    params.BondCompareParameters.CompleteRingsOnly = False
    params.Timeout = int(timeout)
    for left in range(count):
        matrix[left, left] = 1.0
        for right in range(left + 1, count):
            result = rdFMCS.FindMCS(
                [molecules[left], molecules[right]], parameters=params
            )
            if result.canceled:
                raise StepError(
                    "rdkit_mcs_cluster: the partial MCS search timed out; "
                    "simplify the molecules or raise timeout_seconds"
                )
            smaller = max(1, min(atoms[left], atoms[right]))
            value = float(result.numAtoms) / float(smaller)
            matrix[left, right] = matrix[right, left] = value
    return matrix


def cluster_matrix(
    similarity: np.ndarray, distance_cutoff: float
) -> tuple[np.ndarray, list[list[int]]]:
    """Single-linkage clustering from a similarity matrix."""
    count = int(similarity.shape[0])
    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)

    threshold = 1.0 - float(distance_cutoff)
    for left in range(count):
        for right in range(left + 1, count):
            if similarity[left, right] >= threshold - 1e-12:
                union(left, right)
    groups: dict[int, list[int]] = {}
    for index in range(count):
        groups.setdefault(find(index), []).append(index)
    clusters = [sorted(members) for members in groups.values()]
    clusters.sort(key=lambda members: (members[0], len(members)))
    membership = np.zeros((count, len(clusters)), dtype=np.float32)
    for position, members in enumerate(clusters):
        for index in members:
            membership[index, position] = 1.0
    return membership, clusters


class RdkitMcsClusterStep(Step):
    """Group molecules by maximum common substructure similarity."""

    provider = "operon-core"
    parameters_file = "rdkit_mcs_cluster.RdkitMcsClusterStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_mcs_cluster",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit MCS cluster",
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Compute pairwise maximum common substructure similarity with RDKit "
            "and group the molecules by single-linkage clustering."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        smiles = str(params.get("smiles", "") or "")
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        cluster_dim = str(params.get("cluster_dim", "cluster") or "cluster")
        cutoff = float(params.get("distance_cutoff", 0.4))
        timeout = int(params.get("timeout_seconds", 30))
        out_name = params.get("output", self.name)

        if not 0.0 <= cutoff <= 1.0:
            raise StepError(
                "rdkit_mcs_cluster: distance_cutoff must be between 0 and 1"
            )
        if timeout < 1:
            raise StepError("rdkit_mcs_cluster: timeout_seconds must be positive")
        if molecule_dim == cluster_dim:
            raise StepError(
                "rdkit_mcs_cluster: molecule_dim and cluster_dim must differ"
            )
        raw = parse_smiles_text(smiles, "rdkit_mcs_cluster")
        pairs = build_molecules(smiles, "rdkit_mcs_cluster")
        if len(pairs) < 2:
            raise StepError(
                "rdkit_mcs_cluster: at least two molecules are required"
            )
        names = [name for name, _ in pairs]
        smiles_list = [value for _, value in raw]
        molecules = [molecule for _, molecule in pairs]

        similarity = mcs_similarity(molecules, timeout)
        membership, clusters = cluster_matrix(similarity, cutoff)
        sizes = [len(members) for members in clusters]

        out = Form(
            data=membership.astype(np.float32, copy=False),
            dims=[molecule_dim, cluster_dim],
            labels={
                molecule_dim: molecule_labels(names, molecule_dim),
                cluster_dim: {f"cluster{index + 1}": index for index in range(len(clusters))},
            },
            info={
                "missing_code": np.nan,
                "smiles": smiles_list,
                "n_molecules": len(names),
                "distance_cutoff": cutoff,
                "n_clusters": len(clusters),
                "cluster_sizes": sizes,
                "clusters": [
                    [names[index] for index in members] for members in clusters
                ],
                "similarity_matrix": [
                    [round(float(value), 6) for value in row] for row in similarity
                ],
                "metric": "mcs_over_smaller_heavy_atoms",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(names),
            "n_clusters": len(clusters),
            "cluster_sizes": sizes,
            "distance_cutoff": cutoff,
        }
        print(
            f"[rdkit_mcs_cluster] {len(names)} molecule(s) -> "
            f"{len(clusters)} cluster(s) at distance {cutoff}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
