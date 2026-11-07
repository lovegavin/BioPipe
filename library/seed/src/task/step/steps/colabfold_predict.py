"""Structure prediction with the official ColabFold ``colabfold_batch`` runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import read_source
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_MSA_MODES = ("mmseqs2_uniref_env", "mmseqs2_uniref", "single_sequence")


def write_fasta(sequence: str, path: Path, header: str = "query") -> Path:
    """Write a single-sequence FASTA file and return its path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f">{header}\n{sequence}\n", encoding="utf-8")
    return path


def rank_pdb(outdir: Path) -> Path | None:
    """First rank-001 PDB written by ``colabfold_batch`` (relaxed preferred)."""

    for pattern in ("*_relaxed_rank_001_*.pdb", "*_unrelaxed_rank_001_*.pdb"):
        matches = sorted(outdir.glob(pattern))
        if matches:
            return matches[0]
    return None


def parse_scores(path: Path) -> dict:
    """Mean pLDDT, pTM and maximum PAE from a ColabFold scores JSON."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StepError(f"colabfold_predict: cannot read scores {path}: {exc}") from exc
    plddt = np.asarray(payload.get("plddt") or [], dtype=np.float64)
    pae = np.asarray(payload.get("pae") or [], dtype=np.float64)
    if plddt.size == 0 and pae.size == 0:
        raise StepError(f"colabfold_predict: scores {path} carry neither plddt nor pae")
    return {
        "mean_plddt": float(plddt.mean()) if plddt.size else float("nan"),
        "ptm": float(payload["ptm"]) if payload.get("ptm") is not None else float("nan"),
        "max_pae": float(pae.max()) if pae.size else float("nan"),
        "n_residues": int(plddt.size if plddt.size else pae.shape[0]),
    }


def predict(
    sequence: str,
    *,
    binary: str,
    workdir: Path,
    num_models: int = 1,
    num_recycles: int = 3,
    msa_mode: str = "mmseqs2_uniref_env",
    device: str = "cpu",
    timeout: int = 3600,
) -> tuple[Path, Path | None]:
    """Run ``colabfold_batch`` on one sequence and return (structure, scores)."""

    fasta = write_fasta(sequence, workdir / "query.fasta")
    outdir = workdir / "out"
    outdir.mkdir(parents=True, exist_ok=True)
    if binary.lower().endswith(".py"):
        # A script runner (for example a conda entry point or a test double)
        # cannot be executed directly on Windows; start it through Python.
        command = [sys.executable, binary]
    else:
        command = [binary]
    command += [
        fasta.as_posix(),
        outdir.as_posix(),
        "--num-models",
        str(num_models),
        "--num-recycle",
        str(num_recycles),
        "--msa-mode",
        msa_mode,
        "--overwrite",
    ]
    environment = dict(os.environ)
    if device == "cpu":
        environment["CUDA_VISIBLE_DEVICES"] = ""
    elif device == "cuda":
        environment.setdefault("CUDA_VISIBLE_DEVICES", "0")
    try:
        completed = subprocess.run(
            command,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise StepError(
            f"colabfold_predict: '{binary}' is not executable; install ColabFold with "
            "'pip install colabfold[alphafold]' and download the sequence databases"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"colabfold_predict: the predictor timed out after {timeout} s") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-1500:]
        raise StepError(
            f"colabfold_predict: the predictor failed with exit code {completed.returncode}: {tail}"
        )
    structure = rank_pdb(outdir)
    if structure is None:
        raise StepError(
            f"colabfold_predict: the predictor produced no rank-001 structure under {outdir}"
        )
    scores = sorted(outdir.glob("*scores_rank_001*.json"))
    return structure, scores[0] if scores else None


class ColabfoldPredictStep(Step):
    """Predict one structure with the official ColabFold batch runner."""

    provider = "operon-core"

    parameters_file = "colabfold_predict.ColabfoldPredictStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "colabfold_predict",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ColabFold structure prediction",
        "description": (
            "Predict a protein structure from one amino-acid sequence with the official "
            "colabfold_batch runner and return the rank-001 PDB together with the mean pLDDT, "
            "pTM and maximum PAE recorded in the ColabFold scores JSON."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet_map": {"type": "object", "optional": True},
                    },
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        (sequences,) = inputs
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        out_name = str(params.get("output") or "structure")

        sequences_list = decode_sequences(sequences, sequence_dim, position_dim)
        if len(sequences_list) != 1:
            raise StepError(
                f"colabfold_predict: expected exactly one sequence, got {len(sequences_list)}"
            )
        sequence = sequences_list[0]
        if not sequence:
            raise StepError("colabfold_predict: the input sequence is empty")

        binary = str(params.get("colabfold_path") or "colabfold_batch")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else None)
        if resolved is None:
            raise StepError(
                f"colabfold_predict: '{binary}' was not found on PATH; install ColabFold with "
                "'pip install colabfold[alphafold]' and download the sequence databases "
                "(see docs/large_resources.md)"
            )
        num_models = int(params.get("num_models") if params.get("num_models") is not None else 1)
        num_recycles = int(params.get("num_recycles") if params.get("num_recycles") is not None else 3)
        msa_mode = str(params.get("msa_mode") or "mmseqs2_uniref_env")
        device = str(params.get("device") or "cpu")
        timeout = int(params.get("timeout_seconds") if params.get("timeout_seconds") is not None else 3600)
        if msa_mode not in _MSA_MODES:
            raise StepError(
                f"colabfold_predict: msa_mode must be one of {', '.join(_MSA_MODES)}, got '{msa_mode}'"
            )

        workdir = Path(tempfile.mkdtemp(prefix="operon_colabfold_"))
        try:
            structure_path, scores_path = predict(
                sequence,
                binary=resolved,
                workdir=workdir,
                num_models=num_models,
                num_recycles=num_recycles,
                msa_mode=msa_mode,
                device=device,
                timeout=timeout,
            )
            form = read_source(
                structure_path,
                ["atom", "field"],
                {"atom": "auto", "field": "builtin"},
            )
            directory = output_directory(ctx, "colabfold")
            if scores_path is not None:
                saved_scores = directory / (
                    "scores" + (Path(scores_path).suffix or ".json")
                )
                shutil.copyfile(scores_path, saved_scores)
                scores_path = saved_scores
            native_pdb = directory / "prediction.pdb"
            shutil.copyfile(structure_path, native_pdb)
            structure_path = native_pdb
            metrics = (
                parse_scores(scores_path)
                if scores_path is not None
                else {"mean_plddt": float("nan"), "ptm": float("nan"), "max_pae": float("nan"), "n_residues": 0}
            )
            form.info.update(
                {
                    "mean_plddt": metrics["mean_plddt"],
                    "ptm": metrics["ptm"],
                    "max_pae": metrics["max_pae"],
                    "n_residues": metrics["n_residues"],
                    "model_path": str(structure_path),
                    "scores_path": str(scores_path) if scores_path is not None else "",
                    "sequences": [sequence],
                    "msa_mode": msa_mode,
                }
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        result_files = [result_file("structure", structure_path, "pdb", "ColabFold prediction")]
        if scores_path is not None:
            result_files.append(result_file("scores", scores_path, "json", "ColabFold scores"))
        remember_native(ctx, out_name, result_files)
        ctx[out_name] = form
        self._export_data = {
            "result_files": result_files,
            "mean_plddt": metrics["mean_plddt"],
            "ptm": metrics["ptm"],
            "max_pae": metrics["max_pae"],
            "n_residues": metrics["n_residues"],
        }
        print(
            f"[colabfold_predict] {metrics['n_residues']} residues, "
            f"mean pLDDT {metrics['mean_plddt']:.2f}, pTM {metrics['ptm']:.3f}"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
