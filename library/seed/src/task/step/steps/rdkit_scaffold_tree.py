"""Hierarchical Murcko scaffold tree for a molecule collection.

Each molecule contributes one node per scaffold level. Level 1 is the Bemis-Murcko
scaffold, level 2 the scaffold of that scaffold, and so on until the chain becomes
cyclic with nothing to strip (``c1ccccc1`` keeps itself) or empty.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.forms.form import Form
from src.core.errors import StepError
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules

_STATISTICS = ("level", "n_molecules", "n_atoms", "n_bonds")
_MAX_LEVEL = 5


def scaffold_chain(molecule, max_level: int) -> list[str]:
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    chain: list[str] = []
    current = molecule
    for _ in range(max_level):
        try:
            scaffold = MurckoScaffold.GetScaffoldForMol(current)
        except Exception:
            break
        if scaffold is None or scaffold.GetNumHeavyAtoms() == 0:
            break
        smiles = Chem.MolToSmiles(scaffold, isomericSmiles=False)
        if chain and smiles == chain[-1]:
            break
        chain.append(smiles)
        current = scaffold
    return chain


def tree_rows(molecules, max_level: int) -> list[tuple[str, int, int, int, int]]:
    rows: dict[tuple[int, str], list[int]] = {}
    for name, molecule in molecules:
        chain = scaffold_chain(molecule, max_level)
        for level, smiles in enumerate(chain, start=1):
            key = (level, smiles)
            if key not in rows:
                from rdkit import Chem

                parsed = Chem.MolFromSmiles(smiles)
                atoms = parsed.GetNumHeavyAtoms() if parsed is not None else 0
                bonds = parsed.GetNumBonds() if parsed is not None else 0
                rows[key] = [level, 0, int(atoms), int(bonds)]
            rows[key][1] += 1
    ordered = sorted(rows.items(), key=lambda item: (item[0][0], -item[1][1], item[0][1]))
    return [(smiles, level, count, atoms, bonds) for (level, smiles), (_, count, atoms, bonds) in ordered]


class RdkitScaffoldTreeStep(Step):
    provider = "operon-core"
    parameters_file = "rdkit_scaffold_tree.RdkitScaffoldTreeStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_scaffold_tree",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Murcko scaffold tree",
        "description": "Hierarchical scaffold levels shared by a molecule collection.",
        "category": "Machine Learning",
        "icon": "TreeStructure",
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
    }

    def run(self, ctx, inputs) -> None:
        smiles_text = str(ctx.step_params.get("smiles") or "").strip()
        node_dim = str(ctx.step_params.get("node_dim") or "scaffold")
        max_level = ctx.step_params.get("max_level", 3)
        out_name = str(ctx.step_params.get("output") or "scaffolds")

        if not smiles_text:
            raise StepError("rdkit_scaffold_tree: smiles is required; give one 'SMILES [name]' line per molecule")
        if isinstance(max_level, bool) or not isinstance(max_level, int):
            raise StepError("rdkit_scaffold_tree: max_level must be an integer")
        if not 1 <= max_level <= _MAX_LEVEL:
            raise StepError(f"rdkit_scaffold_tree: max_level must be between 1 and {_MAX_LEVEL}")
        molecules = build_molecules(smiles_text, "rdkit_scaffold_tree")
        if not molecules:
            raise StepError("rdkit_scaffold_tree: smiles must contain at least one SMILES line")

        rows = tree_rows(molecules, max_level)
        if not rows:
            raise StepError("rdkit_scaffold_tree: no molecule produced a Murcko scaffold")

        data = np.asarray([[row[1], row[2], row[3], row[4]] for row in rows], dtype=np.float32)
        labels = {
            node_dim: {row[0]: position for position, row in enumerate(rows)},
            "statistic": {name: position for position, name in enumerate(_STATISTICS)},
        }
        out = Form(data=data, dims=[node_dim, "statistic"], labels=labels, info={
            "n_molecules": len(molecules),
            "max_level": max_level,
            "n_nodes": len(rows),
            "levels": {int(row[1]): int(row[2]) for row in rows},
            "missing_code": np.nan,
        })
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "n_nodes": len(rows),
            "max_level": max_level,
            "level_counts": {str(level): count for level, count in out.info["levels"].items()},
        }
        print(f"[rdkit_scaffold_tree] {len(molecules)} molecules, {len(rows)} scaffold nodes")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
