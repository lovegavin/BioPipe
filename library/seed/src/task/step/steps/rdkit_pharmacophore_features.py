"""Pharmacophore feature counts per molecule using RDKit feature definitions."""

from __future__ import annotations

import os
import shutil
import tempfile

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from ._rdkit_common import molecule_labels, parse_smiles_text

_FAMILIES = (
    ("donor", "Donor"),
    ("acceptor", "Acceptor"),
    ("aromatic", "Aromatic"),
    ("hydrophobe", "Hydrophobe"),
    ("lumped_hydrophobe", "LumpedHydrophobe"),
    ("pos_ionizable", "PosIonizable"),
    ("neg_ionizable", "NegIonizable"),
)
_FEATURES = tuple(name for name, _ in _FAMILIES) + ("total",)
_FACTORY = None


def _feature_file() -> str:
    """Return an ASCII-safe path to the RDKit feature definitions.

    RDKit's C++ file reader cannot open paths that contain non-ASCII characters,
    which happens on Windows profiles with a localized user name, so the file is
    copied into a shared ASCII directory when needed.
    """
    from rdkit import RDConfig

    path = os.path.join(RDConfig.RDDataDir, "BaseFeatures.fdef")
    if not os.path.isfile(path):
        raise StepError(f"rdkit_pharmacophore_features: the RDKit feature definition file was not found at '{path}'")
    try:
        path.encode("ascii")
        return path
    except UnicodeEncodeError:
        pass
    base = os.environ.get("ProgramData") or os.environ.get("PUBLIC") or tempfile.gettempdir()
    target = os.path.join(base, "operon", "BaseFeatures.fdef")
    if not os.path.isfile(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(path, target)
    return target


def _factory():
    global _FACTORY
    if _FACTORY is not None:
        return _FACTORY
    from rdkit.Chem import ChemicalFeatures

    _FACTORY = ChemicalFeatures.BuildFeatureFactory(_feature_file())
    return _FACTORY


def feature_row(molecule) -> list[float]:
    from rdkit import Chem

    if molecule.GetNumHeavyAtoms() == 0:
        raise StepError("rdkit_pharmacophore_features: cannot compute pharmacophore features for a molecule without heavy atoms")
    counts = {name: 0 for name, _ in _FAMILIES}
    for feature in _factory().GetFeaturesForMol(molecule):
        family = feature.GetFamily()
        for name, expected in _FAMILIES:
            if family == expected:
                counts[name] += 1
                break
    total = sum(counts.values())
    return [float(counts[name]) for name, _ in _FAMILIES] + [float(total)]


class RdkitPharmacophoreFeaturesStep(Step):
    """Count pharmacophore feature families for a SMILES list."""

    provider = "operon-core"
    parameters_file = "rdkit_pharmacophore_features.RdkitPharmacophoreFeaturesStep.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (64 * 1024 * 1024, 0)

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rdkit_pharmacophore_features",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Pharmacophore Features",
        "description": "Count RDKit pharmacophore feature families for each molecule.",
        "category": "Machine Learning",
        "icon": "CirclesThree",
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
        "dependency_imports": ["numpy", "rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        text = str(params.get("smiles") or "")
        molecule_dim = str(params.get("molecule_dim") or "molecule")
        out_name = str(params.get("output", "features"))
        if not text.strip():
            raise StepError("rdkit_pharmacophore_features: smiles is required; give one 'SMILES [name]' line per molecule")

        from rdkit import Chem

        entries = parse_smiles_text(text, "rdkit_pharmacophore_features")
        names: list[str] = []
        rows: list[list[float]] = []
        details: list[dict] = []
        for name, smiles in entries:
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is None:
                raise StepError(f"rdkit_pharmacophore_features: cannot parse SMILES '{smiles}' for molecule '{name}'")
            values = feature_row(molecule)
            names.append(name)
            rows.append(values)
            details.append(
                {
                    "molecule": name,
                    "smiles": smiles,
                    **{feature: int(values[index]) for index, feature in enumerate(_FEATURES)},
                }
            )

        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[molecule_dim, "feature"],
            labels={
                molecule_dim: molecule_labels(names, molecule_dim),
                "feature": {name: index for index, name in enumerate(_FEATURES)},
            },
            info={
                "missing_code": np.nan,
                "molecules": details,
                "features": list(_FEATURES),
                "n_molecules": len(names),
                "feature_definition": "RDKit BaseFeatures.fdef",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_molecules": len(names),
            "features": list(_FEATURES),
            "mean_total": round(float(data[:, -1].mean()), 6) if len(data) else 0.0,
            "molecules": details,
        }
        print(f"[rdkit_pharmacophore_features] {len(names)} molecules x {len(_FEATURES)} features")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
