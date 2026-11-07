"""structure_ligand_pose_qc: PoseBusters validation suite for a complex."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._protein_common import decode_column

_WATER = {"HOH", "WAT", "DOD"}


def split_complex(form: Form, field_dim: str, ligand_resname: str) -> tuple[str, str]:
    """Return the PDB text for the protein and for the ligand."""

    resnames = decode_column(form, field_dim, "resname")
    chains = decode_column(form, field_dim, "chain")
    numbers = decode_column(form, field_dim, "residue_number")
    atom_names = decode_column(form, field_dim, "atom_name")
    elements = decode_column(form, field_dim, "element")
    protein = []
    ligand = []
    ligand_atoms = 0
    for row in range(form.data.shape[0]):
        resname = str(resnames[row])
        if resname in _WATER:
            continue
        x, y, z = (float(value) for value in form.data[row, :3])
        record = "HETATM" if resname == ligand_resname else "ATOM  "
        line = (
            f"{record}{len(protein) + len(ligand) + 1:5d} {str(atom_names[row])[:4]:<4s} {resname[:3]:>3s} "
            f"{str(chains[row])[:1]}{int(float(numbers[row])):4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {str(elements[row])[:2]:>2s}"
        )
        if resname == ligand_resname:
            ligand.append(line)
            ligand_atoms += 1
        else:
            protein.append(line)
    if ligand_atoms == 0:
        raise StepError(f"structure_ligand_pose_qc: no atom carries the residue name '{ligand_resname}'")
    if not protein:
        raise StepError("structure_ligand_pose_qc: the complex holds no protein atoms beside the ligand")
    return "\n".join(protein) + "\nEND\n", "\n".join(ligand) + "\nEND\n"


def run_posebusters(protein_text: str, ligand_text: str, *, config: str = "dock", workdir: Path | None = None) -> dict:
    """Run the official PoseBusters suite and return the check table."""

    try:
        from posebusters import PoseBusters
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise StepError("structure_ligand_pose_qc: posebusters is required; install it with 'python -m pip install posebusters'") from exc
    workdir = Path(workdir or tempfile.mkdtemp(prefix="posebusters_"))
    workdir.mkdir(parents=True, exist_ok=True)
    protein_path = workdir / "protein.pdb"
    ligand_path = workdir / "ligand.pdb"
    protein_path.write_text(protein_text)
    ligand_path.write_text(ligand_text)
    prediction = ligand_path
    try:
        from rdkit import Chem

        parsed = Chem.MolFromPDBBlock(ligand_text, removeHs=False, sanitize=False)
        if parsed is not None and parsed.GetNumAtoms() > 2:
            Chem.SanitizeMol(parsed)
            sdf_path = workdir / "ligand.sdf"
            Chem.MolToMolFile(parsed, str(sdf_path))
            prediction = sdf_path
    except Exception:  # noqa: BLE001 - keep the PDB route when RDKit cannot parse it
        prediction = ligand_path
    buster = PoseBusters(config=config)
    if config == "mol":
        frame = buster.bust(mol_pred=[str(prediction)])
    else:
        frame = buster.bust(mol_pred=[str(prediction)], mol_cond=str(protein_path))
    row = frame.iloc[0]
    checks = {}
    for column in frame.columns:
        value = row[column]
        if isinstance(value, (bool, np.bool_)):
            checks[str(column)] = float(bool(value))
        elif isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            checks[str(column)] = float(value)
    return {"checks": checks, "n_checks": len(checks), "ligand_path": str(prediction), "protein_path": str(protein_path)}


class StructureLigandPoseQcStep(Step):
    provider = "operon-core"
    parameters_file = "structure_ligand_pose_qc.StructureLigandPoseQcStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "structure_ligand_pose_qc",
        "version": "1.0.0",
        "kind": "operator",
        "title": "配体姿态 PoseBusters 体检",
        "description": (
            "Run the official PoseBusters validation suite on a protein-ligand complex: "
            "sanitisation, bond lengths and angles, internal strain, ring flatness and "
            "protein-ligand volume overlap, reported as one row per check."
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
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["posebusters>=0.3"],
        "dependency_imports": ["posebusters"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("structure_ligand_pose_qc: the structure form is empty")
        field_dim = str(params.get("field_dim", "field"))
        ligand_resname = str(params.get("ligand_resname", "LIG"))
        config = str(params.get("config", "dock"))
        if config not in ("dock", "mol"):
            raise StepError("structure_ligand_pose_qc: config must be 'dock' or 'mol'")
        protein_text, ligand_text = split_complex(form, field_dim, ligand_resname)
        result = run_posebusters(protein_text, ligand_text, config=config)
        checks = result["checks"]
        names = sorted(checks)
        values = np.asarray([[checks[name]] for name in names], dtype=np.float32)
        failures = [name for name in names if checks[name] == 0.0]
        out_dim = str(params.get("check_dim", "check"))
        out_name = str(params.get("output", "pose_qc"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={out_dim: {name: index for index, name in enumerate(names)}, "statistic": {"passed": 0}},
            info={
                "missing_code": np.nan,
                "n_checks": len(names),
                "n_failed": len(failures),
                "failed_checks": failures,
                "config": config,
                "ligand_resname": ligand_resname,
                "ligand_path": result["ligand_path"],
                "protein_path": result["protein_path"],
            },
        )
        self._export_data = {"checks": checks, "n_checks": len(names), "n_failed": len(failures), "failed_checks": failures}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
