"""BRICS fragment overlap between two molecule groups."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules, molecule_labels


def clean_fragment(fragment: str) -> str:
    """Strip BRICS dummy atoms from a fragment SMILES."""

    return fragment.replace("[*]", "").replace("[1*]", "").replace("[2*]", "")


def brics_fragments(molecule, min_size: int = 4) -> set[str]:
    """Heavy-atom BRICS fragments of one molecule, dummies removed."""

    from rdkit.Chem import BRICS

    fragments: set[str] = set()
    for fragment in BRICS.BRICSDecompose(molecule, minFragmentSize=min_size):
        cleaned = clean_fragment(fragment)
        if cleaned:
            fragments.add(cleaned)
    if not fragments:
        from rdkit import Chem

        fragments.add(Chem.MolToSmiles(molecule))
    return fragments


def fragment_sets(smiles_list, min_size: int) -> list[set[str]]:
    """Fragment sets for a molecule list."""

    molecules = build_molecules(smiles_list, "rdkit_fragment_overlap") if isinstance(smiles_list, str) else smiles_list
    return [brics_fragments(molecule, min_size) for molecule in molecules]


def overlap_matrix(first: list[set[str]], second: list[set[str]]) -> np.ndarray:
    """Jaccard overlap of every fragment set in ``first`` against every set in ``second``."""

    matrix = np.zeros((len(first), len(second)), dtype=np.float32)
    for row, left in enumerate(first):
        for column, right in enumerate(second):
            union = left | right
            matrix[row, column] = (len(left & right) / len(union)) if union else 0.0
    return matrix


class RdkitFragmentOverlapStep(Step):
    """Jaccard overlap of BRICS fragment sets between two molecule groups."""

    provider = "operon-core"

    parameters_file = "rdkit_fragment_overlap.RdkitFragmentOverlapStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_fragment_overlap",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit fragment overlap",
        "description": (
            "Compare two molecule groups through their BRICS fragment sets: the output is the "
            "Jaccard overlap (shared / union) of every molecule of the first group against every "
            "molecule of the second group. Groups are given as 'SMILES [name]' lines."
        ),
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
        "dependency_imports": ["numpy", "rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        smiles_a = str(params.get("smiles_a") or "").strip()
        smiles_b = str(params.get("smiles_b") or "").strip()
        min_size = int(params.get("min_fragment_size") if params.get("min_fragment_size") is not None else 4)
        first_dim = str(params.get("molecule_a_dim") or "molecule_a")
        second_dim = str(params.get("molecule_b_dim") or "molecule_b")
        out_name = str(params.get("output") or "fragment_overlap")

        if not smiles_a:
            raise StepError(
                "rdkit_fragment_overlap: smiles_a is required; give one 'SMILES [name]' line per molecule"
            )
        if not smiles_b:
            raise StepError(
                "rdkit_fragment_overlap: smiles_b is required; give one 'SMILES [name]' line per molecule"
            )
        if min_size < 1:
            raise StepError("rdkit_fragment_overlap: min_fragment_size must be at least 1")
        if first_dim == second_dim:
            raise StepError("rdkit_fragment_overlap: molecule_a_dim and molecule_b_dim must differ")

        molecules_a = build_molecules(smiles_a, "rdkit_fragment_overlap")
        molecules_b = build_molecules(smiles_b, "rdkit_fragment_overlap")
        names_a = [name for name, _ in molecules_a]
        names_b = [name for name, _ in molecules_b]
        sets_a = [brics_fragments(molecule, min_size) for _, molecule in molecules_a]
        sets_b = [brics_fragments(molecule, min_size) for _, molecule in molecules_b]
        matrix = overlap_matrix(sets_a, sets_b)

        out = Form(
            data=matrix,
            dims=[first_dim, second_dim],
            labels={
                first_dim: molecule_labels(names_a, first_dim),
                second_dim: molecule_labels(names_b, second_dim),
            },
            info={
                "missing_code": float("nan"),
                "metric": "brics_jaccard",
                "min_fragment_size": min_size,
                "molecules_a": [
                    {"name": name, "n_fragments": len(fragments)}
                    for name, fragments in zip(names_a, sets_a)
                ],
                "molecules_b": [
                    {"name": name, "n_fragments": len(fragments)}
                    for name, fragments in zip(names_b, sets_b)
                ],
                "fragments_a": [sorted(fragments) for fragments in sets_a],
                "fragments_b": [sorted(fragments) for fragments in sets_b],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules_a": len(names_a),
            "n_molecules_b": len(names_b),
            "min_fragment_size": min_size,
            "mean_overlap": round(float(matrix.mean()), 6),
            "max_overlap": round(float(matrix.max()), 6),
            "fragments_a": [len(f) for f in sets_a],
            "fragments_b": [len(f) for f in sets_b],
        }
        print(
            f"[rdkit_fragment_overlap] {len(names_a)} x {len(names_b)} molecules, "
            f"mean Jaccard {matrix.mean():.4f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
