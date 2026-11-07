"""Design only the binder residues that contact a target chain."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from .proteinmpnn_design import MODELS, parse_design_fasta

_STATISTICS = ("score", "global_score", "seq_recovery")
_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def _python(params: dict) -> str:
    configured = params.get("python_executable") or ""
    return str(configured) if configured else sys.executable


def _read_atoms(path: Path) -> list[dict]:
    if not path.is_file():
        raise StepError(f"proteinmpnn_interface_redesign: structure_path '{path}' does not exist")
    atoms: list[dict] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        record = raw[:6].strip().upper()
        if record not in {"ATOM", "HETATM"}:
            continue
        try:
            atoms.append(
                {
                    "record": record,
                    "atom_name": raw[12:16].strip().upper(),
                    "resname": raw[17:20].strip().upper(),
                    "chain": raw[21:22].strip() or "_",
                    "number": int(raw[22:26].strip() or 0),
                    "x": float(raw[30:38]),
                    "y": float(raw[38:46]),
                    "z": float(raw[46:54]),
                    "element": raw[76:78].strip().upper(),
                }
            )
        except (TypeError, ValueError) as exc:
            raise StepError(
                f"proteinmpnn_interface_redesign: malformed coordinate line in '{path}': {raw[:40]}"
            ) from exc
    if not atoms:
        raise StepError(f"proteinmpnn_interface_redesign: '{path}' contains no ATOM/HETATM records")
    return atoms


def _heavy(atom: dict) -> bool:
    element = atom["element"] or atom["atom_name"][:1]
    return element not in {"H", "D"}


def protein_residues(atoms: list[dict], chains: set[str] | None = None) -> dict[str, dict]:
    """Group standard protein residues into ``chain:RES:number`` labels."""
    residues: dict[str, dict] = {}
    for atom in atoms:
        if atom["record"] != "ATOM" or not _heavy(atom):
            continue
        if atom["resname"] not in _THREE_TO_ONE:
            continue
        if chains is not None and atom["chain"] not in chains:
            continue
        label = f"{atom['chain']}:{atom['resname']}:{atom['number']}"
        entry = residues.setdefault(
            label,
            {"chain": atom["chain"], "number": atom["number"], "resname": atom["resname"], "coords": []},
        )
        entry["coords"].append((atom["x"], atom["y"], atom["z"]))
    return residues


def split_chains(text: str) -> list[str]:
    return [part.strip() for part in str(text).replace(";", ",").split(",") if part.strip()]


def interface_residues(
    residues: dict[str, dict], binder: list[str], target: list[str], cutoff: float
) -> list[str]:
    """Return binder residue labels that have a heavy atom near the target."""
    left = {k: v for k, v in residues.items() if v["chain"] in binder}
    right = {k: v for k, v in residues.items() if v["chain"] in target}
    if not left:
        raise StepError("proteinmpnn_interface_redesign: the binder chains have no heavy atoms in the structure")
    if not right:
        raise StepError("proteinmpnn_interface_redesign: the target chains have no heavy atoms in the structure")
    right_tree = cKDTree(np.asarray([c for v in right.values() for c in v["coords"]], dtype=np.float64))
    hits: list[str] = []
    for label, value in left.items():
        coords = np.asarray(value["coords"], dtype=np.float64)
        if right_tree.query_ball_point(coords, r=cutoff).any():
            hits.append(label)
    if not hits:
        raise StepError(
            f"proteinmpnn_interface_redesign: no binder residue is within {cutoff:g} angstrom of the target chains"
        )
    return hits


def fixed_payload(
    stem: str, residues: dict[str, dict], designed: set[str]
) -> dict[str, dict[str, list[int]]]:
    """Fixed positions per chain, keyed by the PDB stem (sequential numbering)."""
    ordered = sorted(residues.items(), key=lambda item: (item[1]["chain"], item[1]["number"]))
    payload: dict[str, list[int]] = {}
    counters: dict[str, int] = {}
    for label, value in ordered:
        chain = value["chain"]
        counters[chain] = counters.get(chain, 0) + 1
        payload.setdefault(chain, [])
        if label not in designed:
            payload[chain].append(counters[chain])
    return {stem: payload}


class ProteinmpnnInterfaceRedesignStep(Step):
    """Redesign the binder interface with the official ProteinMPNN runner."""

    provider = "operon-core"
    parameters_file = "proteinmpnn_interface_redesign.ProteinmpnnInterfaceRedesignStep.parameters.json"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (200 * 1024 * 1024, 0)

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_interface_redesign",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Interface Redesign",
        "description": "Design only binder residues at the target interface with ProteinMPNN.",
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
        "dependencies": ["numpy>=1.24", "scipy>=1.10"],
        "dependency_imports": ["numpy", "scipy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        structure = Path(str(params.get("structure_path") or "")).expanduser()
        repo = Path(str(params.get("proteinmpnn_path") or os.environ.get("OPERON_PROTEINMPNN_PATH") or "")).expanduser()
        model = str(params.get("model_name") or "v_48_020")
        binder = split_chains(params.get("binder_chains", "A"))
        target = split_chains(params.get("target_chains", ""))
        cutoff = float(params.get("cutoff", 8.0))
        count = int(params.get("num_seq_per_target", 4))
        temperature = str(params.get("sampling_temp", "0.1"))
        seed = int(params.get("seed", 1))
        device = str(params.get("device") or "cpu")
        timeout = int(params.get("timeout", 3600))
        out_name = str(ctx.step_params.get("output", "designs"))

        if not structure.is_file():
            raise StepError(f"proteinmpnn_interface_redesign: structure_path '{structure}' does not exist")
        runner = repo / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_interface_redesign: proteinmpnn_path '{repo}' does not contain protein_mpnn_run.py"
            )
        if model not in MODELS:
            raise StepError(f"proteinmpnn_interface_redesign: model_name must be one of {list(MODELS)}, got '{model}'")
        if not 1 <= count <= 500:
            raise StepError("proteinmpnn_interface_redesign: num_seq_per_target must be between 1 and 500")
        if not 0.0 < float(temperature) <= 2.0:
            raise StepError("proteinmpnn_interface_redesign: sampling_temp must be in (0, 2]")
        if seed < 0:
            raise StepError("proteinmpnn_interface_redesign: seed must not be negative")
        if device not in {"cpu", "cuda"}:
            raise StepError("proteinmpnn_interface_redesign: device must be 'cpu' or 'cuda'")
        if not 0.0 < cutoff <= 20.0:
            raise StepError("proteinmpnn_interface_redesign: cutoff must be in (0, 20] angstrom")
        if not binder:
            raise StepError("proteinmpnn_interface_redesign: binder_chains must name at least one chain")

        atoms = _read_atoms(structure)
        present = {atom["chain"] for atom in atoms if atom["record"] == "ATOM"}
        residues = protein_residues(atoms)
        available = sorted({value["chain"] for value in residues.values()})
        missing = [chain for chain in binder + target if chain not in available]
        if missing:
            raise StepError(
                f"proteinmpnn_interface_redesign: chain(s) {sorted(set(missing))} not found in the structure "
                f"(available chains: {available})"
            )
        if not target:
            target = [chain for chain in available if chain not in binder]
        if not target:
            raise StepError("proteinmpnn_interface_redesign: target_chains must name at least one chain")
        overlap = sorted(set(binder) & set(target))
        if overlap:
            raise StepError(f"proteinmpnn_interface_redesign: chain(s) {overlap} cannot be both binder and target")

        hits = interface_residues(residues, binder, target, cutoff)
        designed = set(hits)
        payload = fixed_payload(structure.stem, residues, designed)
        del present

        weights = Path(str(params.get("weights_path") or repo / "vanilla_model_weights")).expanduser()
        if not weights.is_dir():
            raise StepError(f"proteinmpnn_interface_redesign: weights_path '{weights}' is not a directory")

        started = time.time()
        work = Path(tempfile.mkdtemp(prefix="operon-interface-redesign-"))
        try:
            fixed_path = work / "fixed.jsonl"
            fixed_path.write_text(
                "\n".join(__import__("json").dumps(entry) for entry in [payload]) + "\n", encoding="utf-8"
            )
            out_dir = work / "out"
            out_dir.mkdir()
            env = dict(os.environ)
            if device == "cpu":
                env["CUDA_VISIBLE_DEVICES"] = ""
            else:
                env.pop("CUDA_VISIBLE_DEVICES", None)
            command = [
                _python(params),
                "protein_mpnn_run.py",
                "--pdb_path", structure.as_posix(),
                "--out_folder", out_dir.as_posix(),
                "--num_seq_per_target", str(count),
                "--sampling_temp", temperature,
                "--seed", str(seed),
                "--path_to_model_weights", weights.as_posix(),
                "--model_name", model,
                "--suppress_print", "1",
                "--pdb_path_chains", ",".join(binder),
                "--fixed_positions_jsonl", fixed_path.as_posix(),
            ]
            run = subprocess.run(
                command, cwd=str(repo), env=env, capture_output=True, text=True, timeout=timeout
            )
            if run.returncode != 0:
                tail = (run.stderr or run.stdout or "").strip().splitlines()[-3:]
                raise StepError(
                    f"proteinmpnn_interface_redesign: the designer failed with exit code {run.returncode}: "
                    + " | ".join(tail)
                )
            fasta = out_dir / "seqs" / f"{structure.stem}.fa"
            if not fasta.is_file():
                raise StepError(f"proteinmpnn_interface_redesign: the designer produced no FASTA at '{fasta}'")
            designs = parse_design_fasta(fasta)
        except subprocess.TimeoutExpired as exc:
            raise StepError(f"proteinmpnn_interface_redesign: the designer timed out after {timeout} s") from exc
        finally:
            shutil.rmtree(work, ignore_errors=True)

        rows: list[list[float]] = []
        sequences: list[str] = []
        for design in designs:
            values = [float(design["score"]), float(design["global_score"]), float(design["seq_recovery"])]
            if not np.all(np.isfinite(values)):
                raise StepError(
                    "proteinmpnn_interface_redesign: the designer returned a non-finite score; "
                    "check that the PDB carries N, CA, C and O backbone atoms"
                )
            rows.append(values)
            sequences.append(str(design["sequence"]))

        labels = {"design": {f"design{index + 1}": index for index in range(len(rows))},
                  "statistic": {name: index for index, name in enumerate(_STATISTICS)}}
        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["design", "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "sequences": sequences,
                "structure_path": str(structure),
                "interface_residues": sorted(hits),
                "n_interface": len(hits),
                "binder_chains": binder,
                "target_chains": target,
                "cutoff": cutoff,
                "model_name": model,
                "num_seq_per_target": len(rows),
                "sampling_temp": float(temperature),
                "seed": seed,
                "device": device,
                "elapsed_seconds": round(time.time() - started, 3),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_designs": len(rows),
            "n_interface": len(hits),
            "interface_residues": sorted(hits),
            "binder_chains": binder,
            "target_chains": target,
            "sequences": sequences,
        }
        print(
            f"[proteinmpnn_interface_redesign] {len(rows)} designs from {structure.name} "
            f"({len(hits)} interface residues, {time.time() - started:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
