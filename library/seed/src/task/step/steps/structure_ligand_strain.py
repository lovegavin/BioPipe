"""Ligand internal strain from a bound conformation versus its local minimum."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._protein_common import column_index, has_column

_STATISTICS = ("bound_energy", "minimized_energy", "strain_energy")


def _decoded(form: Form, field_dim: str, name: str, value: float) -> str:
    """Decode a label-encoded field back to its original string."""

    encoder = form.info.get("encoders", {}).get("field", {}).get(name)
    code = int(round(float(value)))
    if encoder is None:
        return str(code)
    if hasattr(encoder, "inverse_transform"):
        return str(encoder.inverse_transform([code])[0])
    return str(getattr(encoder, "inverse", {}).get(code, code))


def ligand_block(
    form: Form,
    atom_dim: str,
    field_dim: str,
    resname: str,
    operator: str = "structure_ligand_strain",
) -> tuple[str, int]:
    """Render the selected ligand residue as a PDB block."""

    for name in ("x", "y", "z", "resname", "element"):
        if not has_column(form, field_dim, name):
            raise StepError(f"{operator}: the structure form has no '{name}' column")
    resname_index = column_index(form, field_dim, "resname")
    element_index = column_index(form, field_dim, "element")
    lines: list[str] = []
    serial = 0
    for row in form.data:
        label = _decoded(form, field_dim, "resname", row[resname_index])
        if label.upper() != resname.upper():
            continue
        element = _decoded(form, field_dim, "element", row[element_index])
        serial += 1
        xyz = [float(row[column_index(form, field_dim, axis)]) for axis in ("x", "y", "z")]
        lines.append(
            "HETATM"
            f"{serial:5d}  {element.upper():<2s}  LIG A   1    "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 20.00          {element.upper():>2s}"
        )
    if not lines:
        raise StepError(
            f"{operator}: the structure form carries no residue named '{resname}'"
        )
    if len(lines) < 3:
        raise StepError(
            f"{operator}: the ligand '{resname}' needs at least three atoms for a strain calculation"
        )
    return "\n".join(lines) + "\n", len(lines)


def strain_energy(
    block: str,
    *,
    force_field: str = "MMFF94",
    operator: str = "structure_ligand_strain",
) -> tuple[float, float, float]:
    """Return (bound, minimized, strain) energies in kcal/mol."""

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError as error:  # pragma: no cover - dependency guard
        raise StepError(
            f"{operator}: RDKit is required for the strain calculation; install 'rdkit'"
        ) from error
    molecule = Chem.MolFromPDBBlock(block, removeHs=False, sanitize=True)
    if molecule is None or molecule.GetNumAtoms() == 0:
        raise StepError(f"{operator}: the ligand block could not be sanitized")
    molecule = Chem.AddHs(molecule, addCoords=True)
    ff_name = str(force_field or "MMFF94").upper()
    if ff_name not in ("MMFF94", "UFF"):
        raise StepError(f"{operator}: force_field must be 'MMFF94' or 'UFF'")
    if ff_name == "MMFF94" and not AllChem.MMFFHasAllMoleculeParams(molecule):
        raise StepError(f"{operator}: MMFF94 parameters are missing for this ligand")
    if ff_name == "UFF" and not AllChem.UFFHasAllMoleculeParams(molecule):
        raise StepError(f"{operator}: UFF parameters are missing for this ligand")

    def energy(mol) -> float:
        if ff_name == "MMFF94":
            props = AllChem.MMFFGetMoleculeProperties(mol)
            ff = AllChem.MMFFGetMoleculeForceField(mol, props)
        else:
            ff = AllChem.UFFGetMoleculeForceField(mol)
        if ff is None:
            raise StepError(f"{operator}: the force field could not be constructed")
        return float(ff.CalcEnergy())

    bound = energy(molecule)
    if ff_name == "MMFF94":
        props = AllChem.MMFFGetMoleculeProperties(molecule)
        optimizer = AllChem.MMFFGetMoleculeForceField(molecule, props)
    else:
        optimizer = AllChem.UFFGetMoleculeForceField(molecule)
    optimizer.Minimize(maxIts=5000)
    minimized = float(optimizer.CalcEnergy())
    return bound, minimized, bound - minimized


class StructureLigandStrainStep(Step):
    """Estimate the internal strain of a bound ligand conformation."""

    provider = "operon-core"
    parameters_file = "structure_ligand_strain.StructureLigandStrainStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_strain",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Ligand internal strain",
        "description": (
            "Compute the MMFF94 (or UFF) energy of a bound ligand conformation, "
            "minimize it locally and report the strain energy that the conformation "
            "carries relative to its own minimum."
        ),
        "category": "Structure",
        "icon": "Flask",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "atom_dim"}, {"param": "field_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"encoders": {"type": "object", "optional": True}},
                }
            ],
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
        "dependencies": ["numpy>=1.24", "rdkit>=2023.3"],
        "dependency_imports": ["rdkit"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        atom_dim = str(params.get("atom_dim", "atom")) or "atom"
        field_dim = str(params.get("field_dim", "field")) or "field"
        ligand_dim = str(params.get("ligand_dim", "ligand")) or "ligand"
        out_name = str(params.get("output", "strain")) or "strain"
        resname = str(params.get("ligand_resname", "LIG")).strip() or "LIG"
        force_field = str(params.get("force_field", "MMFF94")).strip() or "MMFF94"
        block, n_atoms = ligand_block(inputs[0], atom_dim, field_dim, resname)
        bound, minimized, strain = strain_energy(block, force_field=force_field)
        ctx[out_name] = Form(
            data=np.asarray([[bound, minimized, strain]], dtype=np.float32),
            dims=[ligand_dim, "statistic"],
            labels={
                ligand_dim: {f"ligand1": 0},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "resname": resname,
                "force_field": force_field.upper(),
                "n_atoms": n_atoms,
                "strain_kcal": strain,
            },
        )
        self._export_data = {
            "resname": resname,
            "force_field": force_field.upper(),
            "n_atoms": n_atoms,
            "strain_energy": strain,
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
