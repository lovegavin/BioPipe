"""Tautomer enumeration and canonical tautomer selection with RDKit."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import molecule_labels, parse_smiles_text

_STATISTICS = (
    "n_tautomers",
    "canonical_changed",
    "canonical_heavy_atoms",
    "canonical_hbd",
    "canonical_hba",
    "n_aromatic_rings",
)


def tautomer_profile(smiles: str, max_tautomers: int = 64) -> dict:
    """Enumerate the tautomers of one SMILES and describe the canonical form."""
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise StepError(f"rdkit_tautomer: cannot parse SMILES {smiles!r}")
    enumerator = rdMolStandardize.TautomerEnumerator()
    enumerator.SetMaxTautomers(int(max_tautomers))
    tautomers = list(enumerator.Enumerate(molecule))
    canonical = enumerator.Canonicalize(molecule)
    canonical_smiles = Chem.MolToSmiles(canonical)
    input_smiles = Chem.MolToSmiles(molecule)
    heavy = canonical.GetNumHeavyAtoms()
    if heavy == 0:
        raise StepError(f"rdkit_tautomer: molecule {smiles!r} has no heavy atoms")
    tautomer_smiles = sorted({Chem.MolToSmiles(item) for item in tautomers} | {canonical_smiles})
    return {
        "input_smiles": input_smiles,
        "canonical_smiles": canonical_smiles,
        "canonical_changed": 0.0 if canonical_smiles == input_smiles else 1.0,
        "n_tautomers": float(len(tautomer_smiles)),
        "canonical_heavy_atoms": float(heavy),
        "canonical_hbd": float(rdMolDescriptors.CalcNumHBD(canonical)),
        "canonical_hba": float(rdMolDescriptors.CalcNumHBA(canonical)),
        "n_aromatic_rings": float(rdMolDescriptors.CalcNumAromaticRings(canonical)),
        "tautomer_smiles": tautomer_smiles,
    }


class RdkitTautomerStep(Step):
    """Enumerate tautomers and report the canonical tautomer of each molecule."""

    provider = 'operon-core'
    parameters_file = 'rdkit_tautomer.RdkitTautomerStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rdkit_tautomer',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Tautomer canonicalization',
        'description': (
            'Enumerate the RDKit tautomers of every input SMILES, pick the '
            'canonical tautomer and report the tautomer count, whether the input '
            'changed, and the canonical hydrogen-bond donor/acceptor counts.'
        ),
        'category': 'Machine Learning',
        'icon': 'Shuffle',
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
        max_tautomers = int(params.get("max_tautomers", 64))
        out_name = params.get("output", self.name)

        if not 1 <= max_tautomers <= 1024:
            raise StepError("rdkit_tautomer: max_tautomers must be between 1 and 1024")
        entries = parse_smiles_text(params.get("smiles", ""), "rdkit_tautomer")
        names = [name for name, _smiles in entries]
        profiles = [tautomer_profile(smiles, max_tautomers) for _name, smiles in entries]
        data = np.asarray(
            [[profile[name] for name in _STATISTICS] for profile in profiles], dtype=np.float32
        )
        form_out = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: molecule_labels(names, molecule_dim),
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "molecules": names,
                "input_smiles": [profile["input_smiles"] for profile in profiles],
                "canonical_smiles": [profile["canonical_smiles"] for profile in profiles],
                "tautomer_smiles": [profile["tautomer_smiles"] for profile in profiles],
                "max_tautomers": max_tautomers,
                "n_molecules": len(profiles),
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_molecules": len(profiles),
            "n_changed": int(data[:, 1].sum()),
            "max_tautomers": max_tautomers,
            "mean_tautomers": round(float(data[:, 0].mean()), 4),
        }
        print(
            f"[{self.name}] {len(profiles)} molecules, "
            f"{int(data[:, 1].sum())} canonicalization changes, "
            f"max {max_tautomers} tautomers per molecule"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
