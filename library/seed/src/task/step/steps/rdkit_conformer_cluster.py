"""Cluster ETKDG conformers of small molecules by heavy-atom RMSD."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_FORCE_FIELDS = ("MMFF94", "MMFF94s", "UFF")


def _embed(molecule, force_field: str, num_conformers: int, max_iterations: int,
           minimize: bool, seed: int):
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.AddHs(molecule)
    if force_field == "UFF":
        if not AllChem.UFFHasAllMoleculeParams(molecule):
            raise StepError(
                "rdkit_conformer_cluster: UFF parameters are not available for molecule"
            )
    elif not AllChem.MMFFHasAllMoleculeParams(molecule):
        raise StepError(
            "rdkit_conformer_cluster: MMFF parameters are not available for molecule"
        )
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    params.pruneRmsThresh = 0.25
    params.numThreads = 1
    conf_ids = list(
        AllChem.EmbedMultipleConfs(
            molecule, numConfs=int(num_conformers), params=params
        )
    )
    if not conf_ids:
        raise StepError("rdkit_conformer_cluster: no conformer could be embedded for molecule")
    if minimize:
        if force_field == "UFF":
            engine = AllChem.UFFGetMoleculeForceField
        else:
            properties = AllChem.MMFFGetMoleculeProperties(
                molecule, mmffVariant=force_field
            )
            engine = lambda conf: AllChem.MMFFGetMoleculeForceField(  # noqa: E731
                molecule, properties, confId=conf
            )
        for conf_id in conf_ids:
            field = engine(conf_id)
            if field is None:
                raise StepError(
                    "rdkit_conformer_cluster: cannot set up the force field for molecule"
                )
            field.Minimize(maxIts=int(max_iterations))
    return molecule, conf_ids


def conformer_rmsds(molecule, conf_ids: list[int]) -> np.ndarray:
    """Pairwise symmetry-corrected heavy-atom RMSD between conformers."""
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    count = len(conf_ids)
    distances = np.zeros((count, count), dtype=np.float64)
    for first in range(count):
        for second in range(first + 1, count):
            probe = Chem.Mol(molecule)
            value = rdMolAlign.GetBestRMS(
                probe, molecule, prbId=conf_ids[first], refId=conf_ids[second]
            )
            distances[first, second] = distances[second, first] = float(value)
    return distances


def cluster_conformers(distances: np.ndarray, cutoff: float) -> list[list[int]]:
    """Butina single-linkage clustering of a condensed distance matrix."""
    from rdkit.ML.Cluster import Butina

    count = int(distances.shape[0])
    if count < 2:
        return [[0]]
    condensed = [
        float(distances[second, first])
        for second in range(1, count)
        for first in range(second)
    ]
    clusters = Butina.ClusterData(
        condensed, count, float(cutoff), isDistData=True, reordering=True
    )
    return [sorted(int(index) for index in cluster) for cluster in clusters]


class RdkitConformerClusterStep(Step):
    provider = "operon-core"
    parameters_file = (
        "rdkit_conformer_cluster.RdkitConformerClusterStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_conformer_cluster",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Conformer clustering",
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit", "numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        smiles_text = str(params.get("smiles") or "").strip()
        if not smiles_text:
            raise StepError(
                "rdkit_conformer_cluster: smiles is required; give one 'SMILES [name]' line per molecule"
            )
        force_field = str(params.get("force_field") or "MMFF94")
        if force_field not in _FORCE_FIELDS:
            raise StepError(
                f"rdkit_conformer_cluster: force_field must be one of {list(_FORCE_FIELDS)}"
            )
        raw_conformers = params.get("num_conformers")
        num_conformers = 10 if raw_conformers is None else int(raw_conformers)
        if not 2 <= num_conformers <= 50:
            raise StepError(
                "rdkit_conformer_cluster: num_conformers must be between 2 and 50"
            )
        raw_iterations = params.get("max_iterations")
        max_iterations = 500 if raw_iterations is None else int(raw_iterations)
        if max_iterations < 1:
            raise StepError(
                "rdkit_conformer_cluster: max_iterations must be positive"
            )
        seed = int(params["seed"]) if params.get("seed") is not None else 20240517
        minimize = bool(params.get("minimize", True))
        raw_cutoff = params.get("cluster_cutoff")
        cutoff = 0.5 if raw_cutoff is None else float(raw_cutoff)
        if not 0.0 < cutoff <= 5.0:
            raise StepError(
                "rdkit_conformer_cluster: cluster_cutoff must be between 0 and 5 angstrom"
            )
        molecule_dim = str(params.get("molecule_dim") or "molecule")
        cluster_dim = str(params.get("cluster_dim") or "cluster")
        if molecule_dim == cluster_dim:
            raise StepError(
                "rdkit_conformer_cluster: molecule_dim and cluster_dim must differ"
            )
        entries = parse_smiles_text(smiles_text, "rdkit_conformer_cluster")
        molecules = build_molecules(smiles_text, "rdkit_conformer_cluster")
        per_molecule: list[dict] = []
        max_clusters = 0
        for name, molecule in molecules:
            embedded, conf_ids = _embed(
                molecule,
                force_field,
                num_conformers,
                max_iterations,
                minimize,
                seed,
            )
            distances = conformer_rmsds(embedded, conf_ids)
            clusters = cluster_conformers(distances, cutoff)
            max_clusters = max(max_clusters, len(clusters))
            per_molecule.append(
                {
                    "name": name,
                    "n_conformers": len(conf_ids),
                    "clusters": clusters,
                }
            )
        data = np.zeros((len(entries), max_clusters), dtype=np.float32)
        cluster_labels: dict[str, int] = {}
        for row_index, entry in enumerate(per_molecule):
            for cluster_index, members in enumerate(entry["clusters"]):
                data[row_index, cluster_index] = float(len(members))
        for cluster_index in range(max_clusters):
            cluster_labels[f"cluster{cluster_index + 1}"] = cluster_index
        labels = {
            molecule_dim: molecule_labels([name for name, _ in entries], molecule_dim),
            cluster_dim: cluster_labels,
        }
        out_name = params["output"]
        form_out = Form(
            data=data,
            dims=[molecule_dim, cluster_dim],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_molecules": len(entries),
                "max_clusters": max_clusters,
                "molecules": per_molecule,
                "force_field": force_field,
                "num_conformers": num_conformers,
                "minimize": minimize,
                "seed": seed,
                "cluster_cutoff": cutoff,
                "unit": "A",
            },
        )
        form_out.validate()
        ctx[out_name] = form_out
        self._export_data = {
            "n_molecules": len(entries),
            "max_clusters": max_clusters,
            "total_conformers": sum(entry["n_conformers"] for entry in per_molecule),
        }
        print(
            f"[rdkit_conformer_cluster] {len(entries)} molecules, "
            f"{self._export_data['total_conformers']} conformers, "
            f"up to {max_clusters} clusters"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
