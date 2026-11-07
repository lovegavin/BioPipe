"""Hashed Morgan fingerprint of each molecule's Murcko scaffold."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._rdkit_common import molecule_labels, parse_smiles_text


def scaffold_fingerprint(smiles: str, *, radius: int = 2, n_bits: int = 512, use_features: bool = False) -> np.ndarray:
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold

    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise StepError(f"rdkit_murcko_fingerprint: cannot parse SMILES {smiles!r}")
    scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
    if scaffold.GetNumHeavyAtoms() == 0:
        return np.zeros(n_bits, dtype=np.float32)
    fingerprint = rdMolDescriptors.GetMorganFingerprintAsBitVect(
        scaffold, radius, nBits=n_bits, useFeatures=use_features
    )
    bits = np.zeros(n_bits, dtype=np.float32)
    for index in fingerprint.GetOnBits():
        bits[int(index)] = 1.0
    return bits


def _integer(params: dict, name: str, default: int, low: int, high: int) -> int:
    value = params.get(name)
    value = default if value is None else value
    if isinstance(value, bool) or not isinstance(value, int):
        raise StepError(f"rdkit_murcko_fingerprint: {name} must be an integer")
    if not low <= value <= high:
        raise StepError(f"rdkit_murcko_fingerprint: {name} must be between {low} and {high}")
    return value


class RdkitMurckoFingerprintStep(Step):
    provider = "operon-core"
    parameters_file = "rdkit_murcko_fingerprint.RdkitMurckoFingerprintStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "version": "1.0.0",
        "id": "rdkit_murcko_fingerprint",
        "kind": "operator",
        "title": "Murcko scaffold fingerprint",
        "description": "Murcko scaffold extraction followed by a hashed Morgan bit fingerprint, one row per molecule.",
        "category": "Machine Learning",
        "icon": "GridNine",
        "contracts": {
            "version": 1,
            "inputs": [],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
        "dependencies": ["numpy>=1.24", "rdkit>=2022.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        text = params.get("smiles")
        if not isinstance(text, str) or not text.strip():
            raise StepError("rdkit_murcko_fingerprint: smiles is required; give one 'SMILES [name]' line per molecule")
        molecule_dim = str(params.get("molecule_dim", "molecule") or "molecule")
        bit_dim = str(params.get("bit_dim", "bit") or "bit")
        out_name = str(params.get("output", "scaffold_fingerprint") or "scaffold_fingerprint")
        radius = _integer(params, "radius", 2, 1, 4)
        n_bits = _integer(params, "n_bits", 512, 64, 4096)
        use_features = bool(params.get("use_features", False))
        if molecule_dim == bit_dim:
            raise StepError("rdkit_murcko_fingerprint: molecule_dim and bit_dim must differ")
        entries = parse_smiles_text(text, "rdkit_murcko_fingerprint")
        rows = [
            scaffold_fingerprint(smiles, radius=radius, n_bits=n_bits, use_features=use_features)
            for _, smiles in entries
        ]
        data = np.asarray(rows, dtype=np.float32)
        labels = molecule_labels([name for name, _ in entries], molecule_dim)
        out = Form(
            data=data,
            dims=[molecule_dim, bit_dim],
            labels={molecule_dim: labels, bit_dim: {str(index): index for index in range(n_bits)}},
            info={
                "missing_code": np.nan,
                "smiles": [smiles for _, smiles in entries],
                "n_molecules": len(entries),
                "radius": radius,
                "n_bits": n_bits,
                "use_features": use_features,
                "on_bits": [int(row.sum()) for row in rows],
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(entries),
            "radius": radius,
            "n_bits": n_bits,
            "use_features": use_features,
            "on_bits": [int(row.sum()) for row in rows],
        }
        print(f"[rdkit_murcko_fingerprint] {len(entries)} scaffolds, {n_bits} bits, radius {radius}")

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
