"""Bemis-Murcko scaffold decomposition of small molecules."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels, parse_smiles_text

_STATISTICS = (
    "scaffold_atoms",
    "scaffold_bonds",
    "ring_count",
    "aromatic_ring_count",
    "side_chain_atoms",
)


class RdkitScaffoldStep(Step):
    provider = 'operon-core'
    """Bemis-Murcko scaffold extraction and ring-system counts."""
    parameters_file = 'rdkit_scaffold.RdkitScaffoldStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'rdkit_scaffold',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'RDKit Bemis-Murcko scaffolds',
     'category': 'Machine Learning',
     'icon': 'TreeStructure',
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
     'description': 'Bemis-Murcko scaffold SMILES plus scaffold and ring-system counts per molecule.'}

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        smiles_text = str(params.get("smiles", "") or "").strip()
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        out_name = params.get("output", self.name)
        if not smiles_text:
            raise StepError(
                "rdkit_scaffold: smiles is required; give one 'SMILES [name]' "
                "line per molecule"
            )
        try:
            from rdkit import Chem
            from rdkit.Chem import rdMolDescriptors
            from rdkit.Chem.Scaffolds import MurckoScaffold
        except ImportError as error:  # pragma: no cover - dependency guard
            raise StepError(
                f"rdkit_scaffold: rdkit is required ({error})"
            ) from error

        molecules = build_molecules(smiles_text, "rdkit_scaffold")
        pairs = parse_smiles_text(smiles_text, "rdkit_scaffold")
        rows: list[list[float]] = []
        scaffold_smiles: list[str] = []
        for name, molecule in molecules:
            try:
                scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
                scaffold_smiles.append(Chem.MolToSmiles(scaffold))
                heavy = int(molecule.GetNumHeavyAtoms())
                scaffold_atoms = int(scaffold.GetNumAtoms())
                rows.append([
                    float(scaffold_atoms),
                    float(scaffold.GetNumBonds()),
                    float(rdMolDescriptors.CalcNumRings(scaffold)),
                    float(rdMolDescriptors.CalcNumAromaticRings(scaffold)),
                    float(max(heavy - scaffold_atoms, 0)),
                ])
            except Exception as error:  # noqa: BLE001 - RDKit raises varied types
                raise StepError(
                    f"rdkit_scaffold: cannot build a scaffold for molecule "
                    f"'{name}': {error}"
                ) from error

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
                "scaffold_smiles": scaffold_smiles,
                "input_smiles": [smiles for _, smiles in pairs],
                "n_molecules": len(molecules),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(molecules),
            "scaffold_smiles": scaffold_smiles,
            "statistics": list(_STATISTICS),
        }
        print(
            f"[rdkit_scaffold] {len(molecules)} molecules, "
            f"{sum(1 for smiles in scaffold_smiles if smiles)} ring scaffolds"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
