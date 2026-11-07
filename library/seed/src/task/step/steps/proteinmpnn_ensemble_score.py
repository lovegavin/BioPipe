"""Score a structure with an ensemble of official ProteinMPNN models."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step
from src.task.step.steps.proteinmpnn_score import (
    MODELS,
    parse_fasta,
    score_files,
    summarize,
)


def parse_models(text: str) -> list[str]:
    """Parse a comma separated model list, preserving order and rejecting dupes."""
    models: list[str] = []
    for piece in str(text or "").replace(" ", ",").split(","):
        name = piece.strip()
        if not name:
            continue
        if name not in MODELS:
            raise StepError(
                f"proteinmpnn_ensemble_score: model '{name}' is unknown; "
                f"choose from {list(MODELS)}"
            )
        if name in models:
            raise StepError(
                f"proteinmpnn_ensemble_score: model '{name}' is listed twice"
            )
        models.append(name)
    if not models:
        raise StepError(
            "proteinmpnn_ensemble_score: models must list at least one model"
        )
    return models


class ProteinmpnnEnsembleScoreStep(Step):
    """Negative log-likelihood of one structure under several ProteinMPNN models."""

    provider = "operon-core"
    parameters_file = "proteinmpnn_ensemble_score.ProteinmpnnEnsembleScoreStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_ensemble_score",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN ensemble score",
        "category": "Machine Learning",
        "icon": "Brain",
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
        "description": (
            "Score a structure with several official ProteinMPNN checkpoints in "
            "--score_only mode and return the per-sequence mean negative "
            "log-likelihood matrix across models."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        structure_path = Path(
            str(params.get("structure_path", "") or "").strip()
        ).expanduser()
        fasta_path = Path(
            str(params.get("fasta_path", "") or "").strip()
        ).expanduser()
        proteinmpnn_path = Path(
            str(params.get("proteinmpnn_path", "") or "").strip()
            or os.environ.get("OPERON_PROTEINMPNN_PATH", "")
        ).expanduser()
        weights_text = str(params.get("weights_path", "") or "").strip()
        python_executable = str(params.get("python_executable", "") or "").strip()
        chains = str(params.get("chains", "") or "").strip()
        seed = int(params.get("seed", 1))
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        timeout = float(params.get("timeout_seconds", 1800.0))
        out_name = params.get("output", self.name)
        models = parse_models(str(params.get("models", ",".join(MODELS))))

        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_ensemble_score: structure_path '{structure_path}' "
                "is not a file"
            )
        if structure_path.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "proteinmpnn_ensemble_score: structure_path must be a .pdb file"
            )
        if not fasta_path.is_file():
            raise StepError(
                f"proteinmpnn_ensemble_score: fasta_path '{fasta_path}' is not a "
                "file"
            )
        if not proteinmpnn_path.is_dir():
            raise StepError(
                "proteinmpnn_ensemble_score: proteinmpnn_path is not a directory "
                "(set OPERON_PROTEINMPNN_PATH or the proteinmpnn_path parameter)"
            )
        runner = proteinmpnn_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_ensemble_score: '{runner}' does not exist"
            )
        weights_path = (
            Path(weights_text).expanduser()
            if weights_text
            else proteinmpnn_path / "vanilla_model_weights"
        )
        for model in models:
            if not (weights_path / f"{model}.pt").is_file():
                raise StepError(
                    f"proteinmpnn_ensemble_score: weights for '{model}' not found "
                    f"in '{weights_path}'"
                )
        if device not in ("cpu", "cuda"):
            raise StepError(
                "proteinmpnn_ensemble_score: device must be 'cpu' or 'cuda'"
            )

        records = parse_fasta(fasta_path)
        command_python = python_executable or sys.executable
        environment = dict(os.environ)
        if device == "cpu":
            environment["CUDA_VISIBLE_DEVICES"] = ""
        else:
            environment.pop("CUDA_VISIBLE_DEVICES", None)

        columns: list[list[float]] = []
        started = time.monotonic()
        out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-ensemble-"))
        try:
            for model in models:
                model_dir = out_dir / model
                command = [
                    command_python,
                    runner.as_posix(),
                    "--pdb_path", structure_path.as_posix(),
                    "--path_to_fasta", fasta_path.as_posix(),
                    "--out_folder", model_dir.as_posix(),
                    "--score_only", "1",
                    "--seed", str(seed),
                    "--path_to_model_weights", weights_path.as_posix(),
                    "--model_name", model,
                    "--suppress_print", "1",
                ]
                if chains:
                    command.extend(["--pdb_path_chains", chains])
                completed = subprocess.run(
                    command,
                    cwd=str(proteinmpnn_path),
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                if completed.returncode != 0:
                    tail = (completed.stderr or completed.stdout or "").strip()
                    raise StepError(
                        "proteinmpnn_ensemble_score: model "
                        f"'{model}' failed with exit code "
                        f"{completed.returncode}: {tail[-800:]}"
                    )
                files = score_files(model_dir, structure_path, len(records))
                missing = [path.name for path in files if not path.is_file()]
                if missing:
                    raise StepError(
                        "proteinmpnn_ensemble_score: the runner produced no "
                        f"score file(s) {missing} for model '{model}'"
                    )
                columns.append([summarize(path)[0] for path in files])
            elapsed = time.monotonic() - started
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

        data = np.asarray(columns, dtype=np.float32).T
        means = data.mean(axis=1)
        spreads = data.max(axis=1) - data.min(axis=1)
        labels = {
            "sequence": {name: position for position, (name, _) in enumerate(records)},
            "model": {model: position for position, model in enumerate(models)},
        }
        out = Form(
            data=data,
            dims=["sequence", "model"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "sequences": [sequence for _, sequence in records],
                "structure_path": str(structure_path),
                "models": list(models),
                "chains": chains or "all",
                "device": device,
                "model_mean_nll": {
                    model: round(float(data[:, position].mean()), 6)
                    for position, model in enumerate(models)
                },
                "sequence_mean_nll": [
                    round(float(value), 6) for value in means
                ],
                "sequence_spread": [round(float(value), 6) for value in spreads],
                "metric": "negative_log_likelihood",
                "elapsed_seconds": round(elapsed, 3),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(records),
            "models": list(models),
            "mean_nll": float(data.mean()),
            "structure_path": str(structure_path),
            "elapsed_seconds": round(elapsed, 3),
        }
        print(
            f"[proteinmpnn_ensemble_score] {len(records)} sequence(s) x "
            f"{len(models)} model(s) from {structure_path.name} "
            f"({device}, {elapsed:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
