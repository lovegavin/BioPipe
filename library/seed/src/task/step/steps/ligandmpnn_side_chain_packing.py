"""Side-chain packing through the official LigandMPNN packer."""

from __future__ import annotations

import json
import shutil
import subprocess
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._native_results import output_directory, remember_native, result_file



class LigandmpnnSideChainPackingStep(Step):
    """Pack side chains of a fixed backbone with the LigandMPNN packer."""

    provider = "operon-core"
    parameters_file = (
        "ligandmpnn_side_chain_packing.LigandmpnnSideChainPackingStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "ligandmpnn_side_chain_packing",
        "version": "1.0.0",
        "kind": "operator",
        "title": "LigandMPNN side-chain packing",
        "description": (
            "Run the official LigandMPNN side-chain packer on a backbone PDB and "
            "return the packed structure as an atom table.  The packer "
            "needs the LigandMPNN repository and its side-chain checkpoint."
        ),
        "category": "Machine Learning",
        "icon": "Cube",
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

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = str(params.get("output", "packed")) or "packed"
        structure = Path(str(params.get("structure_path", "")).strip()).expanduser()
        if not structure.is_file():
            raise StepError(
                f"ligandmpnn_side_chain_packing: structure_path {structure} is not a file"
            )
        if structure.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "ligandmpnn_side_chain_packing: structure_path must name a .pdb or .ent file"
            )
        repo = Path(str(params.get("ligandmpnn_path", "")).strip()).expanduser()
        if not (repo / "run.py").is_file():
            raise StepError(
                f"ligandmpnn_side_chain_packing: {repo}/run.py was not found; "
                "pass ligandmpnn_path pointing at the official LigandMPNN checkout"
            )
        weights_text = str(params.get("weights_path", "")).strip()
        weights = (
            Path(weights_text).expanduser() if weights_text else repo / "model_params"
        )
        checkpoint = str(
            params.get("checkpoint", "ligandmpnn_v_32_010_25.pt")
        ).strip() or "ligandmpnn_v_32_010_25.pt"
        if not (weights / checkpoint).is_file():
            raise StepError(
                f"ligandmpnn_side_chain_packing: checkpoint {weights / checkpoint} "
                "was not found; download it from the official model_params directory"
            )
        sc_checkpoint = str(
            params.get("sc_checkpoint", "ligandmpnn_sc_v_32_002_16.pt")
        ).strip() or "ligandmpnn_sc_v_32_002_16.pt"
        if not (weights / sc_checkpoint).is_file():
            raise StepError(
                "ligandmpnn_side_chain_packing: side-chain checkpoint "
                f"{weights / sc_checkpoint} was not found; download "
                "ligandmpnn_sc_v_32_002_16.pt from the official repository"
            )
        device = str(params.get("device", "cpu")).strip() or "cpu"
        if device not in ("cpu", "cuda"):
            raise StepError("ligandmpnn_side_chain_packing: device must be 'cpu' or 'cuda'")
        chain_text = str(params.get("chains", "")).strip()
        timeout = int(params.get("timeout_seconds", 1800) or 1800)
        model_type = str(params.get("model_type", "ligand_mpnn")).strip() or "ligand_mpnn"
        if model_type not in (
            "protein_mpnn",
            "ligand_mpnn",
            "per_residue_label_membrane_mpnn",
            "global_label_membrane_mpnn",
            "soluble_mpnn",
        ):
            raise StepError(
                "ligandmpnn_side_chain_packing: unknown model_type "
                f"{model_type!r}; use one of the official LigandMPNN model types"
            )
        python_executable = str(params.get("python_executable", "")).strip() or sys.executable

        with tempfile.TemporaryDirectory(prefix="operon_pack_") as tmp:
            out_dir = Path(tmp) / "packed_run"
            out_dir.mkdir()
            command = [
                python_executable,
                str(repo / "run.py"),
                "--pdb_path",
                structure.as_posix(),
                "--out_folder",
                out_dir.as_posix(),
                "--model_type",
                model_type,
                "--checkpoint_ligand_mpnn",
                (weights / checkpoint).as_posix(),
                "--checkpoint_path_sc",
                (weights / sc_checkpoint).as_posix(),
                "--pack_side_chains",
                "1",
                "--number_of_packs_per_design",
                str(int(params.get("number_of_packs_per_design", 1) or 1)),
                "--repack_everything",
                "1" if bool(params.get("repack_everything", False)) else "0",
                "--packed_suffix",
                str(params.get("packed_suffix", "_packed")).strip() or "_packed",
                "--seed",
                str(int(params.get("seed", 0) or 0)),
                "--device",
                device,
                "--verbose",
                "0",
            ]
            if chain_text:
                command += ["--parse_these_chains_only", chain_text]
            env = dict(os.environ)
            env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
            env["CUDA_VISIBLE_DEVICES"] = "" if device == "cpu" else "0"
            env["PYTHONPATH"] = str(repo)
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(repo),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise StepError(
                    f"ligandmpnn_side_chain_packing: the packer timed out after {timeout} s"
                ) from exc
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
                raise StepError(
                    "ligandmpnn_side_chain_packing: the packer failed with exit code "
                    f"{completed.returncode}: {' | '.join(tail)}"
                )
            packed = sorted((out_dir / "packed").glob("*_packed.pdb"))
            if not packed:
                raise StepError(
                    "ligandmpnn_side_chain_packing: the packer produced no packed PDB "
                    f"under {out_dir}"
                )
            form = read_source(
                packed[0], ["atom", "field"], {"atom": "auto", "field": "builtin"}
            )
            directory = output_directory(ctx, "ligandmpnn_packing")
            native_pdb = directory / "packed.pdb"
            shutil.copyfile(packed[0], native_pdb)

        result_files = [result_file("structure", native_pdb, "pdb", "LigandMPNN packed structure")]
        remember_native(ctx, str(out_name), result_files)
        ctx[out_name] = form
        self._export_data = {
            "result_files": result_files,
            "packed_path": packed[0].name,
            "n_atoms": int(form.data.shape[0]),
            "model_type": model_type,
            "packed_suffix": str(params.get("packed_suffix", "_packed")),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
