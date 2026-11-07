"""Functional-group counts from SMARTS patterns.

Each molecule is matched against a small, fixed panel of chemically meaningful
SMARTS definitions; the operator reports how many matches of each group a
molecule contains. This is a fast triage profile, not a molecular-formula
replacement.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules, molecule_labels

# (group name, SMARTS, one match per heavy atom)
GROUPS: tuple[tuple[str, str], ...] = (
    ("carboxyl", "[CX3](=O)[OX2H1]"),
    ("ester", "[CX3](=O)[OX2H0][#6]"),
    ("amide", "[NX3][CX3](=[OX1])"),
    ("ketone", "[#6][CX3](=O)[#6]"),
    ("aldehyde", "[CX3H1](=O)[#6]"),
    ("hydroxyl", "[OX2H]"),
    ("primary_amine", "[NX3H2][#6]"),
    ("secondary_amine", "[NX3H1]([#6])[#6]"),
    ("tertiary_amine", "[NX3H0]([#6])([#6])[#6]"),
    ("nitrile", "[NX1]#[CX2]"),
    ("nitro", "[N+](=O)[O-]"),
    ("thiol", "[SX2H]"),
    ("ether", "[OD2]([#6])[#6]"),
    ("aromatic_ring", "a1aaaaa1"),
    ("halogen", "[F,Cl,Br,I]"),
    ("sulfonamide", "[SX4](=O)(=O)[NX3]"),
    ("phosphate", "[PX4](=O)([OX2])[OX2]"),
)
GROUP_NAMES = tuple(name for name, _ in GROUPS)


def compiled_patterns():
    from rdkit import Chem

    patterns = []
    for name, smiles in GROUPS:
        pattern = Chem.MolFromSmarts(smiles)
        if pattern is None:
            raise StepError(f"rdkit_functional_group_counts: invalid SMARTS for group {name}")
        patterns.append((name, pattern))
    return patterns


def group_counts(molecule, patterns) -> list[int]:
    return [int(len(molecule.GetSubstructMatches(pattern))) for _, pattern in patterns]


class RdkitFunctionalGroupCountsStep(Step):
    provider = "operon-core"
    parameters_file = "rdkit_functional_group_counts.RdkitFunctionalGroupCountsStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_functional_group_counts",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Functional group counts",
        "description": "Count SMARTS-defined functional groups for every input molecule.",
        "category": "Machine Learning",
        "icon": "Flask",
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
        "dependencies": ["numpy>=1.24", "rdkit>=2023.3"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = self.params(ctx)
        text = str(params.get("smiles") or "")
        molecule_dim = str(params.get("molecule_dim") or "molecule")
        group_dim = str(params.get("group_dim") or "group")
        out_name = str(params.get("output") or "groups")

        molecules = build_molecules(text, "rdkit_functional_group_counts")
        patterns = compiled_patterns()
        rows = [group_counts(molecule, patterns) for _, molecule in molecules]
        names = [name for name, _ in molecules]
        out = Form(
            data=np.asarray(rows, dtype=np.float32).reshape(len(rows), len(GROUPS)),
            dims=[molecule_dim, group_dim],
            labels={molecule_dim: molecule_labels(names, molecule_dim), group_dim: {name: index for index, name in enumerate(GROUP_NAMES)}},
            info={
                "missing_code": np.nan,
                "groups": list(GROUP_NAMES),
                "smarts": {name: smiles for name, smiles in GROUPS},
                "n_molecules": len(rows),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_molecules": len(rows), "n_groups": len(GROUPS)}
        print(f"[rdkit_functional_group_counts] {len(rows)} molecules x {len(GROUPS)} groups")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})

    @staticmethod
    def params(ctx) -> dict:
        return dict(ctx.step_params)
