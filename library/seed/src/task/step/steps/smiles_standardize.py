"""Standardize SMILES strings and report their molecular composition."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import (
    build_molecules,
    molecule_labels,
)

_STATISTICS = (
    "n_atoms",
    "n_heavy_atoms",
    "n_fragments",
    "n_rings",
)


class SmilesStandardizeStep(Step):
    """Canonicalize SMILES strings and report basic composition statistics."""

    provider = 'operon-core'
    parameters_file = 'smiles_standardize.SmilesStandardizeStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'smiles_standardize',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Standardize SMILES',
        'description': (
            'Optionally keep the largest fragment, neutralize charges and '
            'write canonical RDKit SMILES for every input molecule.  The '
            'output is a [molecule, statistic] Form with atom, heavy-atom, '
            'fragment and ring counts; the canonical strings are exposed in '
            'info.canonical_smiles.'
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
        from rdkit import Chem
        from rdkit.Chem.MolStandardize import rdMolStandardize

        params = ctx.step_params
        smiles_text = str(params.get("smiles", "")).strip()
        if not smiles_text:
            raise StepError(
                "smiles_standardize: smiles is required; give one "
                "'SMILES [name]' line per molecule"
            )
        keep_largest = bool(params.get("keep_largest_fragment", True))
        neutralize = bool(params.get("neutralize", False))
        molecule_dim = (
            str(params.get("molecule_dim", "molecule")).strip() or "molecule"
        )
        out_name = params.get("output", self.name)

        molecules = build_molecules(smiles_text, "smiles_standardize")
        fragment_chooser = rdMolStandardize.LargestFragmentChooser()
        uncharger = rdMolStandardize.Uncharger()
        canonical: list[str] = []
        statistics: list[list[float]] = []
        input_smiles: list[str] = []
        for name, molecule in molecules:
            try:
                if keep_largest:
                    molecule = fragment_chooser.choose(molecule)
                if neutralize:
                    molecule = uncharger.uncharge(molecule)
            except Exception as error:  # RDKit raises plain RuntimeError
                raise StepError(
                    f"smiles_standardize: cannot standardize molecule "
                    f"'{name}': {error}"
                ) from error
            if molecule is None or molecule.GetNumAtoms() == 0:
                raise StepError(
                    f"smiles_standardize: molecule '{name}' is empty after "
                    "standardization"
                )
            canonical.append(Chem.MolToSmiles(molecule))
            statistics.append(
                [
                    float(molecule.GetNumAtoms()),
                    float(molecule.GetNumHeavyAtoms()),
                    float(len(Chem.GetMolFrags(molecule))),
                    float(molecule.GetRingInfo().NumRings()),
                ]
            )
        input_smiles = [smiles for name, smiles in _input_rows(smiles_text)]
        if len(canonical) != len(input_smiles):
            raise StepError(
                "smiles_standardize: internal error matching input and "
                "standardized molecules"
            )

        data = np.array(statistics, dtype=np.float32)
        form = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: molecule_labels(
                    [name for name, _ in molecules], molecule_dim
                ),
                "statistic": {
                    name: position for position, name in enumerate(_STATISTICS)
                },
            },
            info={
                "canonical_smiles": canonical,
                "input_smiles": input_smiles,
                "keep_largest_fragment": keep_largest,
                "neutralize": neutralize,
                "changed": [
                    standardized != original
                    for standardized, original in zip(canonical, input_smiles)
                ],
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "molecule_dim": molecule_dim,
            "statistics": list(_STATISTICS),
            "canonical_smiles": canonical,
            "input_smiles": input_smiles,
            "keep_largest_fragment": keep_largest,
            "neutralize": neutralize,
        }
        print(f"[{self.name}] {len(canonical)} molecules standardized")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _input_rows(text: str) -> list[tuple[str, str]]:
    from src.task.step.steps._rdkit_common import parse_smiles_text

    return parse_smiles_text(text, "smiles_standardize")
