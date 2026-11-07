"""Ligand-efficiency metrics from SMILES and assay potencies."""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import molecule_labels

_UNIT_TO_MOLAR = {"nm": 1e-9, "um": 1e-6, "mm": 1e-3}
_UNIT_DISPLAY = {"nm": "nM", "um": "uM", "mm": "mM"}
_GAS_CONSTANT = 0.00198720425864083  # kcal / (mol K)


def parse_activity_lines(text) -> list[tuple[str, str, float]]:
    """Parse ``SMILES activity [name]`` lines into (smiles, name, activity)."""

    from rdkit import Chem

    entries: list[tuple[str, str, float]] = []
    count = 0
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split(None, 2)
        if len(fields) < 2:
            raise StepError(
                "ligand_efficiency: each line must be 'SMILES activity [name]', "
                f"got {stripped!r}"
            )
        smiles = fields[0]
        try:
            activity = float(fields[1])
        except ValueError as error:
            raise StepError(
                f"ligand_efficiency: activity {fields[1]!r} is not a number"
            ) from error
        if not math.isfinite(activity) or activity <= 0.0:
            raise StepError("ligand_efficiency: activity must be positive and finite")
        if Chem.MolFromSmiles(smiles) is None:
            raise StepError(f"ligand_efficiency: cannot parse SMILES {smiles!r}")
        count += 1
        name = fields[2].strip() if len(fields) > 2 else f"mol_{count}"
        entries.append((smiles, name, activity))
    if not entries:
        raise StepError("ligand_efficiency: smiles is required; give one 'SMILES activity' line")
    return entries


def efficiency_row(molecule, activity_molar: float, temperature: float) -> list[float]:
    """Return heavy atoms, pActivity, dG, LE, LLE and BEI for one ligand."""

    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

    heavy = int(molecule.GetNumHeavyAtoms())
    weight = float(Descriptors.MolWt(molecule))
    if heavy <= 0 or weight <= 0.0:
        raise StepError("ligand_efficiency: a molecule has no heavy atoms")
    p_activity = -math.log10(activity_molar)
    delta_g = -_GAS_CONSTANT * temperature * math.log(10.0) * p_activity
    ligand_efficiency = -delta_g / heavy
    logp = float(Crippen.MolLogP(molecule))
    lle = p_activity - logp
    bei = 1000.0 * p_activity / weight
    return [
        float(heavy),
        float(p_activity),
        float(delta_g),
        float(ligand_efficiency),
        float(lle),
        float(bei),
    ]


class LigandEfficiencyStep(Step):
    """Ligand efficiency / LLE / BEI from potency values."""

    provider = 'operon-core'
    parameters_file = 'ligand_efficiency.LigandEfficiencyStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'ligand_efficiency',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Ligand efficiency metrics',
        'description': (
            'Parse SMILES with an assay potency, convert the potency to pActivity '
            'and a binding free energy, then report ligand efficiency, lipophilic '
            'ligand efficiency and the binding efficiency index.'
        ),
        'category': 'Machine Learning',
        'icon': 'Scales',
        'contracts': {
            'version': 1,
            'inputs': [],
            'output': {
                'mode': 'declare',
                'schema': {
                    'ndim': 2,
                    'numeric': True,
                    'info_open': True,
                    'axis_info_open': True,
                },
            },
        },
        'resources': {
            'memory_modes': ['full'],
            'supports_cuda': False,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['numpy>=1.24', 'rdkit>=2022.9'],
        'dependency_imports': ['rdkit'],
        'inputs_arity': 0,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        molecule_dim = str(params.get("molecule_dim", "molecule")).strip() or "molecule"
        unit = str(params.get("assay_unit", "nM")).strip().lower()
        temperature = float(params.get("temperature", 298.15))
        out_name = params.get("output", self.name)

        if unit not in _UNIT_TO_MOLAR:
            raise StepError("ligand_efficiency: assay_unit must be 'nM', 'uM' or 'mM'")
        if not 200.0 <= temperature <= 400.0:
            raise StepError("ligand_efficiency: temperature must be between 200 and 400 K")

        from rdkit import Chem

        entries = parse_activity_lines(params.get("smiles", ""))
        scale = _UNIT_TO_MOLAR[unit]
        display_unit = _UNIT_DISPLAY[unit]
        rows: list[list[float]] = []
        details: list[dict] = []
        for smiles, name, activity in entries:
            molecule = Chem.MolFromSmiles(smiles)
            row = efficiency_row(molecule, activity * scale, temperature)
            rows.append(row)
            details.append(
                {
                    "name": name,
                    "smiles": smiles,
                    "activity": activity,
                    "p_activity": round(row[1], 4),
                    "ligand_efficiency": round(row[3], 4),
                }
            )

        labels = molecule_labels([name for _smiles, name, _activity in entries], molecule_dim)
        form_out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: labels,
                "statistic": {
                    "heavy_atoms": 0,
                    "p_activity": 1,
                    "delta_g": 2,
                    "ligand_efficiency": 3,
                    "lle": 4,
                    "bei": 5,
                },
            },
            info={
                "molecules": details,
                "assay_unit": display_unit,
                "temperature": temperature,
                "gas_constant": _GAS_CONSTANT,
                "n_molecules": len(entries),
                "units": {
                    "p_activity": "-log10(molar activity)",
                    "delta_g": "kcal/mol",
                    "ligand_efficiency": "kcal/mol per heavy atom",
                    "bei": "pActivity per kDa",
                },
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_molecules": len(entries),
            "assay_unit": display_unit,
            "temperature": temperature,
            "mean_ligand_efficiency": round(
                float(np.mean([row[3] for row in rows])), 6
            ),
        }
        print(
            f"[{self.name}] {len(entries)} ligands ({display_unit}, {temperature:.1f} K)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
