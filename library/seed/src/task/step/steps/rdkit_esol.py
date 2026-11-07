"""Estimate aqueous solubility with the Delaney/ESOL regression (RDKit)."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_STATISTICS = (
    "mol_logp",
    "molecular_weight",
    "rotatable_bonds",
    "aromatic_atoms",
    "heavy_atoms",
    "aromatic_proportion",
    "esol_log_molar",
    "esol_solubility_mg_l",
)


def esol_row(molecule) -> dict[str, float]:
    """Return the Delaney (2004) ESOL regression terms for one RDKit molecule."""
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    # The regression only applies to neutral, connected structures; salts are
    # accepted but the caller is responsible for keeping the parent molecule.
    heavy_atoms = int(molecule.GetNumHeavyAtoms())
    if heavy_atoms == 0:
        raise StepError("cannot estimate solubility for a molecule without heavy atoms")
    aromatic_atoms = sum(1 for atom in molecule.GetAtoms() if atom.GetIsAromatic())
    molecular_weight = float(Descriptors.MolWt(molecule))
    mol_logp = float(Crippen.MolLogP(molecule))
    rotatable_bonds = int(Lipinski.NumRotatableBonds(molecule))
    aromatic_proportion = aromatic_atoms / heavy_atoms
    esol_log_molar = (
        0.16
        - 0.63 * mol_logp
        - 0.0062 * molecular_weight
        + 0.066 * rotatable_bonds
        - 0.74 * aromatic_proportion
    )
    # rdMolDescriptors is imported to keep the dependency surface explicit for
    # readers of this module; the regression itself uses the terms above.
    _ = rdMolDescriptors
    return {
        "mol_logp": mol_logp,
        "molecular_weight": molecular_weight,
        "rotatable_bonds": float(rotatable_bonds),
        "aromatic_atoms": float(aromatic_atoms),
        "heavy_atoms": float(heavy_atoms),
        "aromatic_proportion": aromatic_proportion,
        "esol_log_molar": esol_log_molar,
        "esol_solubility_mg_l": 10.0**esol_log_molar * molecular_weight * 1000.0,
    }


class RdkitEsolStep(Step):
    """Estimate aqueous solubility with the Delaney/ESOL regression."""

    provider = "operon-core"
    parameters_file = "rdkit_esol.RdkitEsolStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_esol",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit ESOL Solubility",
        "description": (
            "Estimate aqueous molar solubility from SMILES with the Delaney/ESOL linear "
            "regression over cLogP, molecular weight, rotatable bonds and aromatic proportion."
        ),
        "category": "Machine Learning",
        "icon": "ChartLine",
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
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        smiles_text = str(ctx.step_params.get("smiles", ""))
        molecule_dim = str(ctx.step_params.get("molecule_dim", "molecule"))
        output_name = str(ctx.step_params.get("output", "solubility"))
        entries = parse_smiles_text(smiles_text, "rdkit_esol")
        names = [name for name, _ in entries]
        molecules = build_molecules(smiles_text, "rdkit_esol")
        rows = [esol_row(molecule) for _, molecule in molecules]
        values = np.array(
            [[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32
        )
        if not np.all(np.isfinite(values)):
            raise StepError("the ESOL regression produced a non-finite value")
        output = Form(
            data=values,
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: molecule_labels(names, molecule_dim),
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "smiles": [entry[1] for entry in entries],
                "statistics": list(_STATISTICS),
                "n_molecules": len(rows),
                "model": "delaney-esol",
                "solubility_unit": "mol/L (log10) and mg/L",
            },
        )
        output.validate()
        ctx[output_name] = output
        self._export_data = {
            "n_molecules": len(rows),
            "mean_log_solubility": round(float(values[:, 6].mean()), 6),
            "molecules": [
                {"name": name, "smiles": entries[index][1], "esol_log_molar": round(float(values[index, 6]), 6)}
                for index, name in enumerate(names)
            ],
        }
        print(f"[rdkit_esol] {len(rows)} molecules, mean logS {values[:, 6].mean():.4f}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
