"""Prepare a 3D AutoDock PDBQT ligand from SMILES with RDKit."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

_STATISTICS = ("x", "y", "z", "charge", "atomic_number")

# AutoDock 4 atom types keyed by element symbol.
_AD4_TYPES = {
    "C": "A",
    "N": "N",
    "O": "OA",
    "S": "SA",
    "P": "P",
    "H": "H",
    "F": "F",
    "Cl": "Cl",
    "Br": "Br",
    "I": "I",
    "B": "B",
    "Si": "Si",
    "Se": "Se",
    "Zn": "Zn",
    "Mg": "Mg",
    "Ca": "Ca",
    "Fe": "Fe",
    "Mn": "Mn",
}
_POLAR_HYDROGENS = {"N", "O", "S"}


def ad4_type(atom) -> str:
    """Return the AutoDock atom type for an RDKit atom."""

    symbol = atom.GetSymbol()
    if symbol == "H":
        neighbours = list(atom.GetNeighbors())
        if neighbours and neighbours[0].GetSymbol() in _POLAR_HYDROGENS:
            return "HD"
        return "H"
    if symbol not in _AD4_TYPES:
        raise StepError(
            "ligand_pdbqt_prepare: element "
            f"'{symbol}' has no AutoDock 4 atom type"
        )
    return _AD4_TYPES[symbol]


def prepare_molecule(smiles: str, *, seed: int = 0, optimize: bool = True):
    """Embed one SMILES into 3D and assign Gasteiger charges."""

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError as error:  # pragma: no cover - exercised via StepError test
        raise StepError(
            "ligand_pdbqt_prepare: RDKit is required; install it with "
            "'python -m pip install rdkit'"
        ) from error
    text = str(smiles or "").strip()
    if not text:
        raise StepError("ligand_pdbqt_prepare: smiles must not be empty")
    molecule = Chem.MolFromSmiles(text)
    if molecule is None:
        raise StepError(
            f"ligand_pdbqt_prepare: SMILES '{text}' cannot be parsed"
        )
    molecule = Chem.AddHs(molecule)
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = int(seed)
    if AllChem.EmbedMolecule(molecule, parameters) != 0:
        raise StepError(
            "ligand_pdbqt_prepare: RDKit failed to embed a 3D conformer"
        )
    if optimize:
        try:
            AllChem.MMFFOptimizeMolecule(molecule, maxIters=500)
        except Exception:  # noqa: BLE001 - MMFF parameters are not universal
            AllChem.UFFOptimizeMolecule(molecule, maxIters=500)
    AllChem.ComputeGasteigerCharges(molecule)
    return molecule


def pdbqt_lines(molecule, *, name: str = "LIG") -> list[str]:
    """Render an RDKit molecule as PDBQT lines."""

    from rdkit import Chem

    conformer = molecule.GetConformer()
    lines: list[str] = []
    for index, atom in enumerate(molecule.GetAtoms(), start=1):
        position = conformer.GetAtomPosition(atom.GetIdx())
        charge = float(atom.GetProp("_GasteigerCharge")) if atom.HasProp("_GasteigerCharge") else 0.0
        if not np.isfinite(charge):
            charge = 0.0
        label = atom.GetSymbol() + str(index)
        lines.append(
            "ATOM  {serial:5d} {label:<4s} {resname:>3s} A   1    "
            "{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00    {charge:7.3f} {atype:<2s}".format(
                serial=index,
                label=label,
                resname=name,
                x=position.x,
                y=position.y,
                z=position.z,
                charge=charge,
                atype=ad4_type(atom),
            )
        )
    lines.append("TORSDOF 0")
    Chem.SanitizeMol(molecule)
    return lines



def _jsonable(value):
    """Convert numpy values into JSON-serialisable Python objects."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _export_summary(form) -> dict:
    """Build the export payload for one result Form."""
    return {
        "dims": list(form.dims),
        "labels": _jsonable(form.labels),
        "info": _jsonable(
            {key: value for key, value in form.info.items() if key != "missing_code"}
        ),
    }

class LigandPdbqtPrepareStep(Step):
    provider = "biopipe-core"
    parameters_file = "ligand_pdbqt_prepare.LigandPdbqtPrepareStep.parameters.json"
    definition = {
        "protocol_version": 3,
        "id": "ligand_pdbqt_prepare",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Ligand PDBQT preparation",
        "category": "Ligand",
        "icon": "Flask",
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
                    "info": {"missing_code": {"type": ["number", "null"]}},
                },
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "rdkit>=2023.9"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Embed a SMILES ligand in 3D with RDKit, assign Gasteiger charges and "
            "AutoDock 4 atom types, return the atom table and optionally write a "
            "PDBQT file ready for vina_dock."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        smiles = str(params.get("smiles", "") or "").strip()
        molecule = prepare_molecule(
            smiles,
            seed=int(params.get("seed", 0)),
            optimize=bool(params.get("optimize", True)),
        )
        name = str(params.get("resname", "LIG") or "LIG").strip().upper()[:3] or "LIG"
        lines = pdbqt_lines(molecule, name=name)
        output_text = str(params.get("output_path", "") or "").strip()
        written: str | None = None
        if output_text:
            path = Path(output_text).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            written = path.as_posix()

        conformer = molecule.GetConformer()
        rows = []
        for atom in molecule.GetAtoms():
            position = conformer.GetAtomPosition(atom.GetIdx())
            charge = float(atom.GetProp("_GasteigerCharge")) if atom.HasProp("_GasteigerCharge") else 0.0
            if not np.isfinite(charge):
                charge = 0.0
            rows.append(
                (position.x, position.y, position.z, charge, atom.GetAtomicNum())
            )
        data = np.asarray(rows, dtype=np.float32)
        labels = {f"atom{index + 1}": index for index in range(len(rows))}
        result = Form(
            data=data,
            dims=["atom", "statistic"],
            labels={
                "atom": labels,
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "smiles": smiles,
                "n_atoms": len(rows),
                "resname": name,
                "output_path": written,
                "atom_types": sorted({ad4_type(atom) for atom in molecule.GetAtoms()}),
            },
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return self._export_data
