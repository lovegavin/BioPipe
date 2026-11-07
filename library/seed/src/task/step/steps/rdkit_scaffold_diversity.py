"""Murcko scaffold diversity summary for a SMILES collection."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

_STATISTICS = ("n_molecules", "fraction", "mean_scaffold_atoms")


def scaffold_profile(molecule) -> tuple[str, int]:
    """Return (scaffold SMILES, scaffold heavy-atom count) for one molecule."""
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
    if scaffold.GetNumHeavyAtoms() == 0:
        return "acyclic", 0
    return Chem.MolToSmiles(scaffold), int(scaffold.GetNumHeavyAtoms())


def diversity_rows(molecules) -> list[dict]:
    """Aggregate molecules by Murcko scaffold."""
    if not molecules:
        raise StepError("rdkit_scaffold_diversity: at least one molecule is required")
    groups: dict[str, list[int]] = {}
    for molecule in molecules:
        smiles, atoms = scaffold_profile(molecule)
        groups.setdefault(smiles, []).append(atoms)
    total = len(molecules)
    rows = [
        {
            "scaffold": scaffold,
            "n_molecules": len(atoms),
            "fraction": len(atoms) / total,
            "mean_scaffold_atoms": float(np.mean(atoms)) if atoms else 0.0,
        }
        for scaffold, atoms in groups.items()
    ]
    rows.sort(key=lambda row: (-row["n_molecules"], row["scaffold"]))
    return rows


class RdkitScaffoldDiversityStep(Step):
    """Counts how many distinct Murcko scaffolds a SMILES collection contains."""

    provider = "operon-core"
    parameters_file = "rdkit_scaffold_diversity.RdkitScaffoldDiversityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_scaffold_diversity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit Scaffold Diversity",
        "description": (
            "Groups a molecule collection by Murcko scaffold and reports how often each scaffold "
            "occurs, so library diversity and scaffold hopping can be inspected directly."
        ),
        "category": "Machine Learning",
        "icon": "CirclesThree",
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
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (64 * 1024 * 1024, 0)

    def run(self, ctx, inputs) -> None:
        from src.task.step.steps._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

        params = ctx.step_params
        text = str(params.get("smiles", "") or "")
        entries = parse_smiles_text(text, "rdkit_scaffold_diversity")
        if not entries:
            raise StepError("rdkit_scaffold_diversity: smiles must contain at least one SMILES line")
        names = [name for name, _ in entries]
        pairs = build_molecules(text, "rdkit_scaffold_diversity")
        molecules = [molecule for _name, molecule in pairs]
        if not molecules:
            raise StepError("rdkit_scaffold_diversity: no molecule could be parsed")
        scaffold_dim = str(params.get("scaffold_dim", "scaffold"))
        rows = diversity_rows(molecules)
        data = np.asarray(
            [[row["n_molecules"], row["fraction"], row["mean_scaffold_atoms"]] for row in rows],
            dtype=np.float32,
        )
        labels = {str(row["scaffold"]): index for index, row in enumerate(rows)}
        output = Form(
            data=data,
            dims=[scaffold_dim, "statistic"],
            labels={
                scaffold_dim: labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "scaffolds": [row["scaffold"] for row in rows],
                "molecules": names,
                "n_molecules": len(molecules),
                "n_scaffolds": len(rows),
                "scaffold_ratio": len(rows) / len(molecules),
                "most_common": rows[0]["scaffold"] if rows else "",
            },
            axis_info={},
        )
        output.validate()
        output_name = str(params.get("output", "scaffolds"))
        ctx[output_name] = output
        self._export_data = {
            "n_molecules": len(molecules),
            "n_scaffolds": len(rows),
            "scaffold_ratio": len(rows) / len(molecules),
            "most_common": output.info["most_common"],
        }
        print(
            "[rdkit_scaffold_diversity] {} molecules, {} scaffolds".format(len(molecules), len(rows))
        )

    def export(self, ctx) -> dict:
        return dict(getattr(self, "_export_data", {}))
