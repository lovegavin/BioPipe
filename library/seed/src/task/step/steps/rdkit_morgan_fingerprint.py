"""Morgan (circular) fingerprints of SMILES strings as 0/1 Form planes."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import (
    build_molecules,
    molecule_labels,
)


class RdkitMorganFingerprintStep(Step):
    """Compute Morgan fingerprints for a SMILES list."""

    provider = 'operon-core'
    parameters_file = (
        'rdkit_morgan_fingerprint.RdkitMorganFingerprintStep.parameters.json'
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rdkit_morgan_fingerprint',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Morgan fingerprint',
        'description': (
            'Compute the RDKit Morgan (extended connectivity) bit fingerprint '
            'for every SMILES string and return a [molecule, bit] matrix of '
            '0/1 values that downstream clustering or machine-learning '
            'operators can consume.'
        ),
        'category': 'Machine Learning',
        'icon': 'GridNine',
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
        from rdkit.Chem import rdMolDescriptors

        params = ctx.step_params
        smiles_text = str(params.get("smiles", "")).strip()
        if not smiles_text:
            raise StepError(
                "rdkit_morgan_fingerprint: smiles is required; give one "
                "'SMILES [name]' line per molecule"
            )
        radius = int(params.get("radius", 2))
        n_bits = int(params.get("n_bits", 2048))
        use_features = bool(params.get("use_features", False))
        molecule_dim = (
            str(params.get("molecule_dim", "molecule")).strip() or "molecule"
        )
        out_name = params.get("output", self.name)

        if radius < 1 or radius > 6:
            raise StepError(
                "rdkit_morgan_fingerprint: radius must be between 1 and 6"
            )
        if n_bits < 64 or n_bits > 16384:
            raise StepError(
                "rdkit_morgan_fingerprint: n_bits must be between 64 and 16384"
            )

        molecules = build_molecules(smiles_text, "rdkit_morgan_fingerprint")
        rows = []
        on_bits = []
        for _, molecule in molecules:
            fingerprint = rdMolDescriptors.GetMorganFingerprintAsBitVect(
                molecule, radius, nBits=n_bits, useFeatures=use_features
            )
            bits = [int(value) for value in fingerprint.ToBitString()]
            rows.append(bits)
            on_bits.append(sum(bits))

        data = np.array(rows, dtype=np.float32)
        form = Form(
            data=data,
            dims=[molecule_dim, "bit"],
            labels={
                molecule_dim: molecule_labels(
                    [name for name, _ in molecules], molecule_dim
                ),
                "bit": {str(position): position for position in range(n_bits)},
            },
            info={
                "radius": radius,
                "n_bits": n_bits,
                "use_features": use_features,
                "on_bits": on_bits,
                "n_molecules": len(molecules),
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "molecule_dim": molecule_dim,
            "radius": radius,
            "n_bits": n_bits,
            "use_features": use_features,
            "on_bits": on_bits,
            "n_molecules": len(molecules),
        }
        print(
            f"[{self.name}] {len(molecules)} molecules, {n_bits} bits, "
            f"radius {radius}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
