"""Compute the QED drug-likeness score from SMILES (RDKit)."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_STATISTICS = (
    "qed",
    "molecular_weight",
    "mol_logp",
    "tpsa",
    "h_donors",
    "h_acceptors",
    "rotatable_bonds",
    "aromatic_rings",
)


def qed_row(molecule) -> dict[str, float]:
    """Return the QED score plus the descriptors used by its desirability terms."""
    from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors

    if int(molecule.GetNumHeavyAtoms()) == 0:
        raise StepError("cannot compute QED for a molecule without heavy atoms")
    return {
        "qed": float(QED.qed(molecule)),
        "molecular_weight": float(Descriptors.MolWt(molecule)),
        "mol_logp": float(Crippen.MolLogP(molecule)),
        "tpsa": float(rdMolDescriptors.CalcTPSA(molecule)),
        "h_donors": float(Lipinski.NumHDonors(molecule)),
        "h_acceptors": float(Lipinski.NumHAcceptors(molecule)),
        "rotatable_bonds": float(Lipinski.NumRotatableBonds(molecule)),
        "aromatic_rings": float(rdMolDescriptors.CalcNumAromaticRings(molecule)),
    }


class RdkitQedStep(Step):
    """Compute the QED drug-likeness score from RDKit."""

    provider = "operon-core"
    parameters_file = "rdkit_qed.RdkitQedStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_qed",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit QED",
        "description": (
            "Compute the Bickerton quantitative estimate of drug-likeness (QED) from SMILES "
            "together with the descriptor values that feed its desirability terms."
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
        output_name = str(ctx.step_params.get("output", "druglikeness"))
        entries = parse_smiles_text(smiles_text, "rdkit_qed")
        names = [name for name, _ in entries]
        molecules = build_molecules(smiles_text, "rdkit_qed")
        rows = [qed_row(molecule) for _, molecule in molecules]
        values = np.array(
            [[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32
        )
        if not np.all(np.isfinite(values)):
            raise StepError("the QED computation produced a non-finite value")
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
                "model": "bickerton-qed",
                "score_range": [0.0, 1.0],
            },
        )
        output.validate()
        ctx[output_name] = output
        best = float(values[:, 0].max())
        self._export_data = {
            "n_molecules": len(rows),
            "mean_qed": round(float(values[:, 0].mean()), 6),
            "best_qed": round(best, 6),
            "molecules": [
                {
                    "name": name,
                    "smiles": entries[index][1],
                    "qed": round(float(values[index, 0]), 6),
                }
                for index, name in enumerate(names)
            ],
        }
        print(f"[rdkit_qed] {len(rows)} molecules, mean QED {values[:, 0].mean():.4f}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
