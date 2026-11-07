"""Screen ProteinMPNN sampling temperatures for diversity and confidence."""

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
from src.task.step.steps.proteinmpnn_design import MODELS, parse_design_fasta


def parse_temperatures(text: str) -> list[float]:
    """Return the validated, deduplicated and sorted sampling temperatures."""
    pieces = [
        piece.strip()
        for piece in str(text).replace(";", ",").split(",")
        if piece.strip()
    ]
    if not pieces:
        raise StepError(
            "proteinmpnn_temperature_ladder: temperatures must name at least one temperature"
        )
    values: list[float] = []
    for piece in pieces:
        try:
            value = float(piece)
        except ValueError as exc:
            raise StepError(
                "proteinmpnn_temperature_ladder: temperature "
                f"'{piece}' is not a number"
            ) from exc
        if not 0.0 < value <= 1.0:
            raise StepError(
                "proteinmpnn_temperature_ladder: temperature "
                f"{value:g} must be in (0, 1]"
            )
        values.append(round(value, 4))
    unique = sorted(set(values))
    if len(unique) > 5:
        raise StepError(
            "proteinmpnn_temperature_ladder: at most five temperatures are supported"
        )
    return unique


def pairwise_identity(sequences: list[str]) -> float:
    """Mean pairwise sequence identity over all design pairs."""
    if len(sequences) < 2:
        return 0.0
    length = len(sequences[0])
    if length == 0:
        raise StepError(
            "proteinmpnn_temperature_ladder: designs must not be empty"
        )
    matches = 0
    pairs = 0
    for first in range(len(sequences)):
        for second in range(first + 1, len(sequences)):
            if len(sequences[second]) != length:
                raise StepError(
                    "proteinmpnn_temperature_ladder: designs have different lengths"
                )
            matches += sum(
                1
                for left, right in zip(sequences[first], sequences[second])
                if left == right
            )
            pairs += 1
    return matches / (pairs * length)


class ProteinmpnnTemperatureLadderStep(Step):
    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_temperature_ladder"
        ".ProteinmpnnTemperatureLadderStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_temperature_ladder",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN 温度梯度",
        "description": "在同一骨架上扫描多个采样温度，比较序列多样性与打分。",
        "category": "Machine Learning",
        "icon": "SlidersHorizontal",
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        structure = str(params.get("structure_path", "")).strip()
        if not structure:
            raise StepError(
                "proteinmpnn_temperature_ladder: structure_path is required; point it "
                "at a PDB file"
            )
        structure_path = Path(structure)
        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_temperature_ladder: structure_path '{structure}' is not a file"
            )
        repo = str(params.get("proteinmpnn_path", "")).strip()
        if not repo:
            repo = os.environ.get("OPERON_PROTEINMPNN_PATH", "").strip()
        if not repo:
            raise StepError(
                "proteinmpnn_temperature_ladder: proteinmpnn_path is required; point it "
                "at the official ProteinMPNN checkout"
            )
        repo_path = Path(repo)
        runner = repo_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_temperature_ladder: '{repo}' must contain "
                "protein_mpnn_run.py"
            )
        weights_text = str(params.get("weights_path", "")).strip()
        weights_path = (
            Path(weights_text) if weights_text else repo_path / "vanilla_model_weights"
        )
        if not weights_path.is_dir():
            raise StepError(
                "proteinmpnn_temperature_ladder: weights_path "
                f"'{weights_path}' is not a directory"
            )
        model_name = str(params.get("model_name", "v_48_020"))
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_temperature_ladder: model_name must be one of {list(MODELS)}"
            )
        temperatures = parse_temperatures(
            str(params.get("temperatures", "0.1,0.3"))
        )
        num_sequences = int(params.get("num_seq_per_target", 4))
        if num_sequences < 2:
            raise StepError(
                "proteinmpnn_temperature_ladder: num_seq_per_target must be at least 2 "
                "to measure diversity"
            )
        seed = int(params.get("seed", 1))
        if seed < 0:
            raise StepError(
                "proteinmpnn_temperature_ladder: seed must not be negative"
            )
        chains = str(params.get("chains", "")).strip().replace(" ", "")
        device = str(params.get("device", "cpu"))
        if device not in {"cpu", "cuda"}:
            raise StepError(
                "proteinmpnn_temperature_ladder: device must be 'cpu' or 'cuda'"
            )
        timeout = float(params.get("timeout", 1800.0))
        if timeout <= 0:
            raise StepError(
                "proteinmpnn_temperature_ladder: timeout must be positive"
            )
        temperature_dim = str(params.get("temperature_dim", "temperature"))
        output = str(params.get("output", "ladder"))

        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        per_temperature: dict[str, list[str]] = {}
        started = time.monotonic()
        for temperature in temperatures:
            out_dir = Path(tempfile.mkdtemp(prefix="operon-ladder-"))
            try:
                command = [
                    _python(params),
                    runner.as_posix(),
                    "--pdb_path", structure_path.as_posix(),
                    "--out_folder", out_dir.as_posix(),
                    "--num_seq_per_target", str(num_sequences),
                    "--sampling_temp", f"{temperature:g}",
                    "--seed", str(seed),
                    "--path_to_model_weights", weights_path.as_posix(),
                    "--model_name", model_name,
                    "--suppress_print", "1",
                ]
                if chains:
                    command.extend(["--pdb_path_chains", chains])
                environment = dict(os.environ)
                if device == "cpu":
                    environment["CUDA_VISIBLE_DEVICES"] = ""
                else:
                    environment.pop("CUDA_VISIBLE_DEVICES", None)
                completed = subprocess.run(
                    command,
                    cwd=repo_path,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
                if completed.returncode != 0:
                    tail = (completed.stderr or completed.stdout or "").strip()[-800:]
                    raise StepError(
                        "proteinmpnn_temperature_ladder: protein_mpnn_run.py failed for "
                        f"T={temperature:g} with exit code {completed.returncode}: {tail}"
                    )
                fasta = out_dir / "seqs" / f"{structure_path.stem}.fa"
                if not fasta.is_file():
                    raise StepError(
                        "proteinmpnn_temperature_ladder: the designer produced no FASTA "
                        f"for T={temperature:g} at {fasta}"
                    )
                designs = parse_design_fasta(fasta)
                if not designs:
                    raise StepError(
                        "proteinmpnn_temperature_ladder: the designer FASTA for "
                        f"T={temperature:g} has no generated designs"
                    )
                sequences = [record["sequence"] for record in designs]
                scores = [float(record["score"]) for record in designs]
                recoveries = [float(record["seq_recovery"]) for record in designs]
                identity = pairwise_identity(sequences)
                rows.append(
                    [
                        float(np.mean(scores)),
                        float(np.mean(recoveries)),
                        1.0 - identity,
                        float(len(sequences)),
                    ]
                )
                labels[f"{temperature:g}"] = len(labels)
                per_temperature[f"{temperature:g}"] = sequences
            except subprocess.TimeoutExpired as exc:
                raise StepError(
                    "proteinmpnn_temperature_ladder: the designer timed out after "
                    f"{timeout:.0f}s"
                ) from exc
            finally:
                shutil.rmtree(out_dir, ignore_errors=True)

        ctx[output] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[temperature_dim, "statistic"],
            labels={
                temperature_dim: labels,
                "statistic": {
                    "mean_score": 0,
                    "mean_seq_recovery": 1,
                    "diversity": 2,
                    "n_designs": 3,
                },
            },
            info={
                "missing_code": np.nan,
                "temperatures": temperatures,
                "sequences_per_temperature": per_temperature,
                "model_name": model_name,
                "seed": seed,
                "chains": chains,
                "device": device,
                "structure_path": str(structure_path),
            },
        )
        elapsed = time.monotonic() - started
        self._export_data = {
            "temperatures": temperatures,
            "model_name": model_name,
            "n_designs": num_sequences,
            "mean_score": [round(row[0], 4) for row in rows],
            "mean_seq_recovery": [round(row[1], 4) for row in rows],
            "diversity": [round(row[2], 4) for row in rows],
            "elapsed_seconds": round(elapsed, 3),
        }
        print(
            f"[proteinmpnn_temperature_ladder] {len(temperatures)} temperatures on "
            f"{structure_path.name} ({elapsed:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _python(params: dict) -> str:
    executable = str(params.get("python_executable", "")).strip()
    if executable:
        return executable
    return sys.executable
