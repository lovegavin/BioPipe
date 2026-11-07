"""Seeded random-SMILES enumeration for augmentation and invariance checks."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._rdkit_common import build_molecules, molecule_labels

_STATISTICS = ("n_variants", "n_unique", "mean_length", "max_length")
_MAX_VARIANTS = 200


def random_smiles(molecule, count: int, seed: int) -> list[str]:
    """Return ``count`` random SMILES strings for one molecule."""

    from rdkit import Chem

    strings = list(Chem.MolToRandomSmilesVect(molecule, count, randomSeed=seed))
    return [str(value) for value in strings]


def augment_row(molecule, count: int, seed: int) -> tuple[list[str], list[float]]:
    """Enumerate random SMILES and summarise the variant set."""

    variants = random_smiles(molecule, count, seed)
    if not variants:
        raise StepError("rdkit_smiles_augment: the molecule produced no SMILES variants")
    unique = list(dict.fromkeys(variants))
    lengths = [float(len(value)) for value in variants]
    row = [
        float(len(variants)),
        float(len(unique)),
        float(np.mean(lengths)),
        float(max(lengths)),
    ]
    return variants, row


class RdkitSmilesAugmentStep(Step):
    """Enumerate random SMILES variants for every input molecule."""

    provider = "operon-core"
    parameters_file = "rdkit_smiles_augment.RdkitSmilesAugmentStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_smiles_augment",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RDKit SMILES Augment",
        "description": (
            "Enumerate seeded random SMILES strings for every molecule and report how many "
            "variants are unique along with their length statistics."
        ),
        "category": "Machine Learning",
        "icon": "Shuffle",
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

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        smiles = params.get("smiles", "")
        molecule_dim = str(params.get("molecule_dim", "molecule"))
        raw_count = params.get("n_variants", 5)
        count = 5 if raw_count is None else int(raw_count)
        raw_seed = params.get("seed", 42)
        seed = 42 if raw_seed is None else int(raw_seed)
        out_name = str(params.get("output", "augment") or "augment")
        if count < 1 or count > _MAX_VARIANTS:
            raise StepError(
                f"rdkit_smiles_augment: n_variants must be between 1 and {_MAX_VARIANTS}"
            )
        if seed < 0:
            raise StepError("rdkit_smiles_augment: seed must not be negative")
        molecules = build_molecules(smiles, "rdkit_smiles_augment")
        rows: list[list[float]] = []
        variants_all: list[list[str]] = []
        details: list[dict] = []
        for name, molecule in molecules:
            variants, row = augment_row(molecule, count, seed)
            rows.append(row)
            variants_all.append(variants)
            details.append(
                {
                    "name": name,
                    "n_variants": len(variants),
                    "n_unique": len(list(dict.fromkeys(variants))),
                }
            )
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[molecule_dim, "statistic"],
            labels={
                molecule_dim: molecule_labels([name for name, _ in molecules], molecule_dim),
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "molecules": [name for name, _ in molecules],
                "variants": variants_all,
                "seed": seed,
                "n_variants": count,
                "details": details,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(rows),
            "seed": seed,
            "n_variants": count,
            "molecules": [name for name, _ in molecules],
            "variant_counts": [len(value) for value in variants_all],
            "unique_counts": [len(set(value)) for value in variants_all],
            "mean_unique": round(float(data[:, 1].mean()), 6),
        }
        print(
            f"[rdkit_smiles_augment] {len(rows)} molecules, {count} variants each, "
            f"mean unique {float(data[:, 1].mean()):.2f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
