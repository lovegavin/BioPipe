"""Rule-based drug-likeness panel for small molecules."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_STATISTICS = (
    "molecular_weight",
    "mol_logp",
    "tpsa",
    "h_donors",
    "h_acceptors",
    "rotatable_bonds",
    "ring_count",
    "lipinski_violations",
    "veber_pass",
    "ghose_pass",
)

# Ghose filter bounds (Ghose, Viswanadhan & Wendoloski, 1999).
_GHOSE_MW = (160.0, 480.0)
_GHOSE_LOGP = (-0.4, 5.6)
_GHOSE_ATOMS = (20, 70)
_GHOSE_MR = (40.0, 130.0)


class RdkitAdmetRulesStep(Step):
    provider = 'operon-core'
    """Lipinski, Veber and Ghose drug-likeness rules per molecule."""
    parameters_file = 'rdkit_admet_rules.RdkitAdmetRulesStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'rdkit_admet_rules',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'RDKit drug-likeness rules',
     'category': 'Machine Learning',
     'icon': 'Scales',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'rdkit>=2022.9'],
     'dependency_imports': ['rdkit'],
     'inputs_arity': 0,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Descriptor panel plus Lipinski, Veber and Ghose pass/fail flags per molecule.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        smiles_text = str(params.get("smiles", "") or "").strip()
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        mw_max = float(params.get("mw_max", 500.0))
        logp_max = float(params.get("logp_max", 5.0))
        hbd_max = int(params.get("hbd_max", 5))
        hba_max = int(params.get("hba_max", 10))
        tpsa_max = float(params.get("tpsa_max", 140.0))
        rotb_max = int(params.get("rotatable_bonds_max", 10))
        out_name = params.get("output", self.name)
        if not smiles_text:
            raise StepError(
                "rdkit_admet_rules: smiles is required; give one 'SMILES [name]' "
                "line per molecule"
            )
        if mw_max <= 0:
            raise StepError("rdkit_admet_rules: mw_max must be positive")
        if logp_max <= 0:
            raise StepError("rdkit_admet_rules: logp_max must be positive")
        if hbd_max < 0 or hba_max < 0:
            raise StepError("rdkit_admet_rules: hbd_max and hba_max must not be negative")
        if tpsa_max <= 0:
            raise StepError("rdkit_admet_rules: tpsa_max must be positive")
        if rotb_max < 0:
            raise StepError("rdkit_admet_rules: rotatable_bonds_max must not be negative")
        try:
            from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(f"rdkit_admet_rules: rdkit is required ({error})") from error

        molecules = build_molecules(smiles_text, "rdkit_admet_rules")
        pairs = parse_smiles_text(smiles_text, "rdkit_admet_rules")
        rows: list[list[float]] = []
        parent_smiles: list[str] = []
        details: list[dict] = []
        for name, molecule in molecules:
            try:
                heavy = int(molecule.GetNumHeavyAtoms())
                mw = float(Descriptors.MolWt(molecule))
                logp = float(Crippen.MolLogP(molecule))
                tpsa = float(rdMolDescriptors.CalcTPSA(molecule))
                hbd = int(Lipinski.NumHDonors(molecule))
                hba = int(Lipinski.NumHAcceptors(molecule))
                rotb = int(Lipinski.NumRotatableBonds(molecule))
                rings = int(rdMolDescriptors.CalcNumRings(molecule))
                mr = float(Crippen.MolMR(molecule))
            except Exception as error:  # noqa: BLE001 - RDKit raises varied types
                raise StepError(
                    f"rdkit_admet_rules: cannot describe molecule '{name}': {error}"
                ) from error

            violations = (
                int(mw > mw_max)
                + int(logp > logp_max)
                + int(hbd > hbd_max)
                + int(hba > hba_max)
            )
            veber_pass = int(rotb <= rotb_max and tpsa <= tpsa_max)
            ghose_pass = int(
                _GHOSE_MW[0] <= mw <= _GHOSE_MW[1]
                and _GHOSE_LOGP[0] <= logp <= _GHOSE_LOGP[1]
                and _GHOSE_ATOMS[0] <= heavy <= _GHOSE_ATOMS[1]
                and _GHOSE_MR[0] <= mr <= _GHOSE_MR[1]
            )
            rows.append([
                mw, logp, tpsa, float(hbd), float(hba), float(rotb), float(rings),
                float(violations), float(veber_pass), float(ghose_pass),
            ])
            parent_smiles.append(name)
            details.append({
                "name": name,
                "smiles": pairs[len(parent_smiles) - 1][1],
                "molar_refractivity": mr,
                "heavy_atoms": heavy,
                "veber_pass": bool(veber_pass),
                "ghose_pass": bool(ghose_pass),
            })

        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: molecule_labels([name for name, _ in molecules], molecule_dim),
                "statistic": {
                    name: position for position, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "molecules": details,
                "statistics": list(_STATISTICS),
                "thresholds": {
                    "mw_max": mw_max,
                    "logp_max": logp_max,
                    "hbd_max": hbd_max,
                    "hba_max": hba_max,
                    "tpsa_max": tpsa_max,
                    "rotatable_bonds_max": rotb_max,
                },
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "passing_lipinski": int(
                sum(1 for row in rows if row[7] == 0.0)
            ),
            "passing_veber": int(sum(1 for row in rows if row[8] == 1.0)),
            "passing_ghose": int(sum(1 for row in rows if row[9] == 1.0)),
            "statistics": list(_STATISTICS),
        }
        print(
            f"[rdkit_admet_rules] {len(molecules)} molecules, "
            f"{self._export_data['passing_lipinski']} without Lipinski violations"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
