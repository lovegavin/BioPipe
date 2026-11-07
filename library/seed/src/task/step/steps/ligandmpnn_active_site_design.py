"""Design only the residues around a bound ligand with the official LigandMPNN."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from .ligandmpnn_design import _cuda_available, _python, _repo_path, parse_design_fasta

_STATISTICS = ("overall_confidence", "ligand_confidence", "seq_recovery")
_RESIDUE_NAMES = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q",
    "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K",
    "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
    "TYR": "Y", "VAL": "V",
}
_SOLVENT = {"HOH", "WAT", "DOD"}


def parse_structure(path: Path) -> list[dict]:
    """Parse PDB ATOM/HETATM records into flat atom dictionaries."""

    atoms: list[dict] = []
    if not path.exists():
        raise StepError(f"ligandmpnn_active_site_design: structure not found: {path}")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        record = line[:6].strip()
        if record not in ("ATOM", "HETATM"):
            continue
        element = line[76:78].strip().upper() or line[12:16].strip()[:1].upper()
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            number = int(line[22:26])
        except ValueError:
            raise StepError(
                f"ligandmpnn_active_site_design: malformed coordinate line in {path.name}: "
                f"{line.rstrip()}"
            )
        atoms.append(
            {
                "record": record,
                "name": line[12:16].strip(),
                "resname": line[17:20].strip().upper(),
                "chain": line[21:22].strip() or "_",
                "number": number,
                "icode": line[26:27].strip(),
                "element": element,
                "xyz": np.array([x, y, z], dtype=np.float64),
            }
        )
    if not atoms:
        raise StepError(
            f"ligandmpnn_active_site_design: no ATOM/HETATM records in {path}"
        )
    return atoms


def ligand_atoms(atoms: list[dict], resnames: str) -> list[dict]:
    """Return the heavy atoms that belong to the ligand residues of interest."""

    wanted = {value.strip().upper() for value in str(resnames).split(",") if value.strip()}
    selected = [
        atom
        for atom in atoms
        if atom["record"] == "HETATM"
        and atom["resname"] in wanted
        and atom["element"] not in ("H", "D")
    ]
    if not selected:
        raise StepError(
            "ligandmpnn_active_site_design: no ligand heavy atom matches "
            f"ligand_resnames '{resnames}'"
        )
    return selected


def active_site(atoms: list[dict], ligand: list[dict], cutoff: float) -> list[dict]:
    """Find protein residues with at least one heavy atom within ``cutoff`` of the ligand."""

    if cutoff <= 0 or cutoff > 20:
        raise StepError(
            "ligandmpnn_active_site_design: cutoff must be in (0, 20] angstrom"
        )
    protein = [
        atom
        for atom in atoms
        if atom["record"] == "ATOM"
        and atom["resname"] in _RESIDUE_NAMES
        and atom["element"] not in ("H", "D")
    ]
    if not protein:
        raise StepError(
            "ligandmpnn_active_site_design: the structure has no standard protein residues"
        )
    coordinates = np.asarray([atom["xyz"] for atom in ligand], dtype=np.float64)
    rows: list[dict] = []
    for atom in protein:
        distances = np.linalg.norm(coordinates - atom["xyz"], axis=1)
        if float(distances.min()) <= cutoff:
            rows.append(atom)
    if not rows:
        raise StepError(
            "ligandmpnn_active_site_design: no protein residue is within "
            f"{cutoff} angstrom of the ligand"
        )
    unique: dict[str, dict] = {}
    for atom in rows:
        label = (
            f"{atom['chain']}{atom['number']}{atom['icode']}".strip()
        )
        unique.setdefault(label, atom)
    return list(unique.values())


def protein_residues(atoms: list[dict]) -> dict[str, dict]:
    """Collect standard protein residues as ordered ``chain+number`` keyed entries."""

    residues: dict[str, dict] = {}
    for atom in atoms:
        if atom["record"] != "ATOM" or atom["resname"] not in _RESIDUE_NAMES:
            continue
        key = f"{atom['chain']}{atom['number']}{atom['icode']}".strip()
        residues.setdefault(key, atom)
    return residues


def fixed_positions(residues: dict[str, dict], active: list[dict]) -> list[str]:
    """Return the protein residue identifiers that must stay fixed."""

    active_keys = {f"{atom['chain']}{atom['number']}{atom['icode']}".strip() for atom in active}
    return sorted(key for key in residues if key not in active_keys)


class LigandmpnnActiveSiteDesignStep(Step):
    """Redesign ligand-proximal residues while keeping the rest of the protein fixed."""

    provider = "operon-core"
    parameters_file = (
        "ligandmpnn_active_site_design.LigandmpnnActiveSiteDesignStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "ligandmpnn_active_site_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "LigandMPNN Active Site Design",
        "description": (
            "Find the protein residues around a bound ligand and let the official "
            "LigandMPNN redesign only those positions while the rest of the structure "
            "stays fixed."
        ),
        "category": "Machine Learning",
        "icon": "Intersect",
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
            "supports_cuda": True,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list) -> None:
        params = ctx.step_params
        structure = Path(str(params.get("structure_path", ""))).expanduser()
        repo = _repo_path(str(params.get("ligandmpnn_path", "") or ""))
        weights = params.get("weights_path", "") or ""
        python = _python(str(params.get("python_executable", "") or ""))
        ligand_resnames = str(params.get("ligand_resnames", "LIG") or "LIG")
        chains = str(params.get("chains", "") or "").strip()
        raw_samples = params.get("num_seq_per_target", 8)
        count = 8 if raw_samples is None else int(raw_samples)
        raw_temperature = params.get("temperature", 0.1)
        temperature = 0.1 if raw_temperature is None else float(raw_temperature)
        raw_cutoff = params.get("cutoff", 8.0)
        cutoff = 8.0 if raw_cutoff is None else float(raw_cutoff)
        raw_seed = params.get("seed", 1)
        seed = 1 if raw_seed is None else int(raw_seed)
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        raw_timeout = params.get("timeout", 1800)
        timeout = 1800 if raw_timeout is None else int(raw_timeout)
        out_name = str(params.get("output", "designs") or "designs")
        if not structure.is_file():
            raise StepError(
                f"ligandmpnn_active_site_design: structure_path must point at a PDB file, "
                f"got '{structure}'"
            )
        if count < 1:
            raise StepError(
                "ligandmpnn_active_site_design: num_seq_per_target must be at least 1"
            )
        if temperature <= 0 or temperature > 5:
            raise StepError(
                "ligandmpnn_active_site_design: temperature must be in (0, 5]"
            )
        if device not in ("cpu", "cuda"):
            raise StepError(
                "ligandmpnn_active_site_design: device must be 'cpu' or 'cuda'"
            )
        atoms = parse_structure(structure)
        ligand = ligand_atoms(atoms, ligand_resnames)
        active = active_site(atoms, ligand, cutoff)
        residues = protein_residues(atoms)
        fixed = fixed_positions(residues, active)
        if not fixed:
            raise StepError(
                "ligandmpnn_active_site_design: every protein residue is in the active "
                "site; nothing would stay fixed"
            )
        runner = repo / "run.py"
        if not runner.is_file():
            raise StepError(
                f"ligandmpnn_active_site_design: {runner} does not exist; set "
                "ligandmpnn_path to an official LigandMPNN checkout"
            )
        active_labels = [
            f"{atom['chain']}{atom['number']}{atom['icode']}".strip() for atom in active
        ]
        out_dir = Path(tempfile.mkdtemp(prefix="operon-ligandmpnn-active-"))
        try:
            command = [
                python,
                str(runner),
                "--model_type",
                "ligand_mpnn",
                "--pdb_path",
                structure.as_posix(),
                "--out_folder",
                out_dir.as_posix(),
                "--fixed_residues",
                " ".join(fixed),
                "--number_of_batches",
                str(count),
                "--temperature",
                str(temperature),
                "--seed",
                str(seed),
                "--batch_size",
                "1",
            ]
            if weights:
                weights_path = Path(weights).expanduser()
                if not weights_path.is_file():
                    raise StepError(
                        "ligandmpnn_active_site_design: weights_path must point at a "
                        f"LigandMPNN checkpoint, got '{weights_path}'"
                    )
                command += ["--checkpoint_ligand_mpnn", weights_path.as_posix()]
            if chains:
                command += ["--chains_to_design", chains]
            env = dict(os.environ)
            env["CUDA_VISIBLE_DEVICES"] = (
                "" if device == "cpu" else env.get("CUDA_VISIBLE_DEVICES", "0")
            )
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(repo),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                raise StepError(
                    "ligandmpnn_active_site_design: the designer timed out after "
                    f"{timeout} s"
                )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()[-800:]
                raise StepError(
                    "ligandmpnn_active_site_design: the designer failed with exit code "
                    f"{completed.returncode}: {tail}"
                )
            fasta = out_dir / "seqs" / f"{structure.stem}.fa"
            if not fasta.is_file():
                raise StepError(
                    "ligandmpnn_active_site_design: the designer produced no FASTA at "
                    f"{fasta}"
                )
            designs = parse_design_fasta(fasta)
            if not designs:
                raise StepError(
                    "ligandmpnn_active_site_design: the designer FASTA has no generated "
                    "designs"
                )
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
        rows: list[list[float]] = []
        sequences: list[str] = []
        for design in designs:
            rows.append(
                [
                    float(design["overall_confidence"]),
                    float(design["ligand_confidence"]),
                    float(design["seq_recovery"]),
                ]
            )
            sequences.append(str(design["sequence"]))
        data = np.asarray(rows, dtype=np.float32)
        if not np.isfinite(data).all():
            raise StepError(
                "ligandmpnn_active_site_design: the designer returned non-finite "
                "confidence values"
            )
        out = Form(
            data=data,
            dims=["design", "statistic"],
            labels={
                "design": {
                    f"design{index + 1}": index for index in range(len(rows))
                },
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "structure_path": str(structure),
                "ligand_resnames": ligand_resnames,
                "n_ligand_atoms": len(ligand),
                "cutoff": cutoff,
                "active_site_residues": active_labels,
                "fixed_residues": fixed,
                "n_fixed": len(fixed),
                "sequences": sequences,
                "model_type": "ligand_mpnn",
                "weights_path": weights,
                "temperature": temperature,
                "seed": seed,
                "device": device,
                "metric": "overall_confidence",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(rows),
            "n_active_site": len(active_labels),
            "n_fixed": len(fixed),
            "ligand_resnames": ligand_resnames,
            "cutoff": cutoff,
            "mean_confidence": round(float(data[:, 0].mean()), 6),
            "sequences": sequences,
        }
        print(
            f"[ligandmpnn_active_site_design] {len(rows)} designs, "
            f"{len(active_labels)} active-site residues redesigned, {len(fixed)} fixed"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
