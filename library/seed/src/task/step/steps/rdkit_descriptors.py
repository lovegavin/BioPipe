"""Lipinski/PCA-style molecular descriptors for SMILES strings."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import (
    build_molecules,
    molecule_labels,
    parse_smiles_text,
)


def _descriptor_functions():
    """Return (name, callable) pairs; imports RDKit lazily."""
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    return (
        ("molecular_weight", Descriptors.MolWt),
        ("logp", Crippen.MolLogP),
        ("molar_refractivity", Crippen.MolMR),
        ("tpsa", rdMolDescriptors.CalcTPSA),
        ("hbond_donors", Lipinski.NumHDonors),
        ("hbond_acceptors", Lipinski.NumHAcceptors),
        ("rotatable_bonds", rdMolDescriptors.CalcNumRotatableBonds),
        ("ring_count", rdMolDescriptors.CalcNumRings),
        ("aromatic_ring_count", rdMolDescriptors.CalcNumAromaticRings),
        ("heavy_atoms", lambda molecule: molecule.GetNumHeavyAtoms()),
        ("heteroatoms", rdMolDescriptors.CalcNumHeteroatoms),
        ("fraction_csp3", rdMolDescriptors.CalcFractionCSP3),
    )


class RdkitDescriptorsStep(Step):
    """Compute twelve RDKit molecular descriptors for a SMILES list."""

    provider = 'operon-core'
    parameters_file = 'rdkit_descriptors.RdkitDescriptorsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rdkit_descriptors',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'RDKit molecular descriptors',
        'description': (
            'Parse SMILES strings with RDKit and compute twelve standard '
            'descriptors (molecular weight, Crippen logP and molar '
            'refractivity, TPSA, hydrogen-bond donors and acceptors, '
            'rotatable bonds, ring counts, heavy and hetero atom counts and '
            'the fraction of sp3 carbons).'
        ),
        'category': 'Machine Learning',
        'icon': 'Dna',
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
        smiles_text = str(params.get("smiles", "")).strip()
        if not smiles_text:
            raise StepError(
                "rdkit_descriptors: smiles is required; give one "
                "'SMILES [name]' line per molecule"
            )
        molecule_dim = str(params.get("molecule_dim", "molecule")).strip() or "molecule"
        out_name = params.get("output", self.name)

        pairs = parse_smiles_text(smiles_text, "rdkit_descriptors")
        molecules = build_molecules(smiles_text, "rdkit_descriptors")
        functions = _descriptor_functions()
        names = [name for name, _ in functions]
        matrix = [
            [float(function(molecule)) for _, function in functions]
            for _, molecule in molecules
        ]
        data = np.array(matrix, dtype=np.float32)
        if not np.all(np.isfinite(data)):
            raise StepError(
                "rdkit_descriptors: RDKit returned a non-finite descriptor; "
                "check the input molecules"
            )

        form = Form(
            data=data,
            dims=[molecule_dim, "descriptor"],
            labels={
                molecule_dim: molecule_labels(
                    [name for name, _ in molecules], molecule_dim
                ),
                "descriptor": {
                    name: position for position, name in enumerate(names)
                },
            },
            info={
                "smiles": [smiles for _, smiles in pairs],
                "descriptors": names,
                "n_molecules": len(molecules),
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "molecule_dim": molecule_dim,
            "descriptors": names,
            "smiles": [smiles for _, smiles in pairs],
            "n_molecules": len(molecules),
        }
        print(
            f"[{self.name}] {len(molecules)} molecules, {len(names)} descriptors"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
