"""Rule-based oral bioavailability flags from SMILES (RDKit descriptors)."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_STATISTICS = (
    "molecular_weight",
    "mol_logp",
    "tpsa",
    "h_donors",
    "h_acceptors",
    "rotatable_bonds",
    "n_lipinski_violations",
    "lipinski_pass",
    "veber_pass",
    "egan_pass",
    "oral_bioavailability_pass",
)


def bioavailability_row(
    molecule,
    *,
    mw_max: float = 500.0,
    logp_max: float = 5.0,
    hbd_max: float = 5.0,
    hba_max: float = 10.0,
    tpsa_max: float = 140.0,
    rotatable_max: float = 10.0,
    egan_tpsa_max: float = 131.6,
    egan_logp_max: float = 5.88,
) -> dict[str, float]:
    """Return descriptor values and the Lipinski, Veber and Egan pass flags."""
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    if int(molecule.GetNumHeavyAtoms()) == 0:
        raise StepError(
            "cannot score oral bioavailability for a molecule without heavy atoms"
        )
    molecular_weight = float(Descriptors.MolWt(molecule))
    mol_logp = float(Crippen.MolLogP(molecule))
    tpsa = float(rdMolDescriptors.CalcTPSA(molecule))
    h_donors = float(Lipinski.NumHDonors(molecule))
    h_acceptors = float(Lipinski.NumHAcceptors(molecule))
    rotatable_bonds = float(Lipinski.NumRotatableBonds(molecule))

    violations = (
        int(molecular_weight > mw_max)
        + int(mol_logp > logp_max)
        + int(h_donors > hbd_max)
        + int(h_acceptors > hba_max)
    )
    lipinski_pass = violations <= 1
    veber_pass = rotatable_bonds <= rotatable_max and tpsa <= tpsa_max
    egan_pass = tpsa <= egan_tpsa_max and mol_logp <= egan_logp_max
    return {
        "molecular_weight": molecular_weight,
        "mol_logp": mol_logp,
        "tpsa": tpsa,
        "h_donors": h_donors,
        "h_acceptors": h_acceptors,
        "rotatable_bonds": rotatable_bonds,
        "n_lipinski_violations": float(violations),
        "lipinski_pass": float(lipinski_pass),
        "veber_pass": float(veber_pass),
        "egan_pass": float(egan_pass),
        "oral_bioavailability_pass": float(
            lipinski_pass and veber_pass and egan_pass
        ),
    }


class RdkitOralBioavailabilityStep(Step):
    """Flag rule-based oral bioavailability from RDKit descriptors."""

    provider = "operon-core"
    parameters_file = (
        "rdkit_oral_bioavailability.RdkitOralBioavailabilityStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_oral_bioavailability",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit Oral Bioavailability Rules",
        "description": (
            "Evaluate the Lipinski, Veber and Egan rule sets for oral bioavailability from "
            "SMILES and report descriptor values, violations and a combined pass flag."
        ),
        "category": "Machine Learning",
        "icon": "Funnel",
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
        output_name = str(ctx.step_params.get("output", "bioavailability"))
        entries = parse_smiles_text(smiles_text, "rdkit_oral_bioavailability")
        names = [name for name, _ in entries]
        molecules = build_molecules(smiles_text, "rdkit_oral_bioavailability")
        limits = {
            "mw_max": float(ctx.step_params.get("mw_max", 500.0)),
            "logp_max": float(ctx.step_params.get("logp_max", 5.0)),
            "hbd_max": float(ctx.step_params.get("hbd_max", 5.0)),
            "hba_max": float(ctx.step_params.get("hba_max", 10.0)),
            "tpsa_max": float(ctx.step_params.get("tpsa_max", 140.0)),
            "rotatable_max": float(ctx.step_params.get("rotatable_bonds_max", 10.0)),
            "egan_tpsa_max": float(ctx.step_params.get("egan_tpsa_max", 131.6)),
            "egan_logp_max": float(ctx.step_params.get("egan_logp_max", 5.88)),
        }
        rows = [
            bioavailability_row(molecule, **limits) for _, molecule in molecules
        ]
        values = np.array(
            [[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32
        )
        if not np.all(np.isfinite(values)):
            raise StepError("the bioavailability rules produced a non-finite value")
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
                "rule_sets": ["lipinski", "veber", "egan"],
                "thresholds": limits,
                "note": (
                    "lipinski_pass allows one violation, matching the common Ro5 "
                    "'at most one failure' interpretation."
                ),
            },
        )
        output.validate()
        ctx[output_name] = output
        passing = int(values[:, 10].sum())
        self._export_data = {
            "n_molecules": len(rows),
            "n_passing": passing,
            "molecules": [
                {
                    "name": name,
                    "smiles": entries[index][1],
                    "oral_bioavailability_pass": bool(values[index, 10]),
                    "lipinski_violations": int(values[index, 6]),
                }
                for index, name in enumerate(names)
            ],
        }
        print(
            f"[rdkit_oral_bioavailability] {len(rows)} molecules, "
            f"{passing} pass all rule sets"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
