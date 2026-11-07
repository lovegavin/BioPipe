"""Formal and Gasteiger charge summaries per molecule."""

from __future__ import annotations

import numpy as np
from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import build_molecules

STATISTICS = (
    "formal_charge",
    "n_positive_atoms",
    "n_negative_atoms",
    "sum_gasteiger",
    "mean_abs_gasteiger",
    "max_gasteiger",
    "min_gasteiger",
)


def gasteiger_charges(molecule) -> list[float]:
    """Return per-atom Gasteiger charges (zeros for atoms RDKit cannot type)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    probe = Chem.Mol(molecule)
    AllChem.ComputeGasteigerCharges(probe)
    charges: list[float] = []
    for atom in probe.GetAtoms():
        value = atom.GetDoubleProp("_GasteigerCharge")
        if value != value or value in (float("inf"), float("-inf")):
            value = 0.0
        charges.append(float(value))
    return charges


def charge_row(molecule) -> list[float]:
    heavy = [atom for atom in molecule.GetAtoms() if atom.GetAtomicNum() > 1]
    if not heavy:
        return [0.0] * len(STATISTICS)
    charges = np.asarray(gasteiger_charges(molecule), dtype=float)
    heavy_index = [atom.GetIdx() for atom in heavy]
    heavy_charges = charges[heavy_index]
    formal = np.asarray([atom.GetFormalCharge() for atom in heavy], dtype=float)
    return [
        float(formal.sum()),
        float(np.sum(formal > 0)),
        float(np.sum(formal < 0)),
        float(heavy_charges.sum()),
        float(np.mean(np.abs(heavy_charges))),
        float(heavy_charges.max()),
        float(heavy_charges.min()),
    ]


class RdkitChargeProfileStep(Step):
    """Formal-charge and Gasteiger summaries for a set of molecules."""

    provider = "operon-core"
    parameters_file = "rdkit_charge_profile.RdkitChargeProfileStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_charge_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit charge profile",
        "description": (
            "Reports formal charge, charged atom counts and Gasteiger charge summaries "
            "for each molecule."
        ),
        "category": "Machine Learning",
        "icon": "Scales",
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
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        out_name = str(params.get("output", "charges"))
        smiles = params.get("smiles")
        if not isinstance(smiles, str) or not smiles.strip():
            raise StepError(
                "rdkit_charge_profile: smiles is required; give one 'SMILES [name]' line "
                "per molecule"
            )
        molecules = build_molecules(smiles, "rdkit_charge_profile")
        rows = [charge_row(molecule) for _, molecule in molecules]
        labels = [name for name, _ in molecules]
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: {label: index for index, label in enumerate(labels)},
                "statistic": {
                    name: index for index, name in enumerate(STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_molecules": len(labels),
                "statistics": list(STATISTICS),
                "charge_model": "gasteiger",
            },
        )
        out.validate()
        matrix = np.asarray(rows)
        self._export_data = {
            "n_molecules": len(labels),
            "neutral_molecules": int(np.sum(np.abs(matrix[:, 0]) < 1e-6)),
            "charged_molecules": int(np.sum(np.abs(matrix[:, 0]) >= 1e-6)),
            "mean_abs_gasteiger": float(matrix[:, 4].mean()),
        }
        ctx[out_name] = out
        print(
            f"[rdkit_charge_profile] {len(labels)} molecules, "
            f"{self._export_data['charged_molecules']} charged"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
