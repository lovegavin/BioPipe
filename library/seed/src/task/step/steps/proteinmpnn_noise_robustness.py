"""ProteinMPNN design robustness across backbone coordinate noise levels.

Each replicate perturbs the atom coordinates with zero-mean Gaussian noise and
redesigns the structure with the official ProteinMPNN runner, so the reported
sequence recovery and model scores describe how sensitive a design task is to
small backbone displacements rather than to sampling randomness.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps.proteinmpnn_design import MODELS, parse_design_fasta

_STATISTICS = (
    "sigma",
    "replicate",
    "n_designs",
    "mean_score",
    "mean_global_score",
    "mean_seq_recovery",
    "min_seq_recovery",
)
_MAX_LEVELS = 5
_MAX_REPLICATES = 5


def parse_levels(text: str) -> list[float]:
    """Parse the comma-separated noise levels, in angstroms."""

    tokens = [token for token in str(text).replace(",", " ").split() if token]
    if not tokens:
        raise StepError(
            "proteinmpnn_noise_robustness: noise_levels must list at least one "
            "non-negative number"
        )
    levels: list[float] = []
    for token in tokens:
        try:
            value = float(token)
        except ValueError as error:
            raise StepError(
                f"proteinmpnn_noise_robustness: noise level '{token}' is not a "
                "number"
            ) from error
        if value < 0:
            raise StepError(
                f"proteinmpnn_noise_robustness: noise level {value} must be >= 0"
            )
        if value in levels:
            raise StepError(
                f"proteinmpnn_noise_robustness: noise level {value} is repeated"
            )
        levels.append(value)
    if len(levels) > _MAX_LEVELS:
        raise StepError(
            "proteinmpnn_noise_robustness: at most "
            f"{_MAX_LEVELS} noise levels are supported"
        )
    return sorted(levels)


def pdb_coordinates(text: str) -> tuple[np.ndarray, list[int]]:
    """Return the coordinates of every coordinate record and their line indices."""

    rows: list[tuple[float, float, float]] = []
    lines: list[int] = []
    for index, line in enumerate(text.splitlines()):
        if line[:6] not in ("ATOM  ", "HETATM"):
            continue
        rows.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
        lines.append(index)
    if not rows:
        raise StepError(
            "proteinmpnn_noise_robustness: the structure file carries no "
            "ATOM/HETATM coordinates"
        )
    return np.asarray(rows, dtype=np.float64), lines


def perturb_coordinates(
    coordinates: np.ndarray, sigma: float, rng: np.random.Generator
) -> np.ndarray:
    """Add independent Gaussian displacements to every coordinate."""

    if sigma <= 0:
        return coordinates.copy()
    return coordinates + rng.normal(0.0, sigma, size=coordinates.shape)


def write_perturbed(text: str, lines: list[int], coordinates: np.ndarray) -> str:
    """Rewrite the coordinate columns of the selected records."""

    parts = text.splitlines(keepends=True)
    for position, line_index in enumerate(lines):
        x, y, z = coordinates[position]
        original = parts[line_index]
        prefix = original[:30]
        suffix = original[54:]
        newline = "\n" if original.endswith("\n") else ""
        if suffix.endswith("\n"):
            suffix = suffix[:-1]
        parts[line_index] = (
            f"{prefix}{x:8.3f}{y:8.3f}{z:8.3f}{suffix}{newline}"
        )
    return "".join(parts)


def noise_row(records: list[dict], sigma: float, replicate: int) -> tuple[float, ...]:
    scores = np.array([record["score"] for record in records], dtype=np.float64)
    globals_ = np.array([record["global_score"] for record in records], dtype=np.float64)
    recoveries = np.array(
        [record["seq_recovery"] for record in records], dtype=np.float64
    )
    return (
        sigma,
        float(replicate),
        float(len(records)),
        float(scores.mean()),
        float(globals_.mean()),
        float(recoveries.mean()),
        float(recoveries.min()),
    )


def run_replicate(
    params: dict,
    repo: Path,
    runner: Path,
    weights: Path | None,
    structure: Path,
    chain: str,
    timeout: float,
) -> list[dict]:
    """Run the official ProteinMPNN runner and return the design records."""

    model_name = str(params.get("model_name") or "v_48_020")
    count = int(params.get("num_seq_per_target") or 8)
    temperature = str(params.get("sampling_temp") or "0.1")
    seed = int(params.get("seed") or 0)
    device = str(params.get("device") or "cpu").strip().lower()
    if model_name not in MODELS:
        raise StepError(
            "proteinmpnn_noise_robustness: model_name must be one of "
            f"{', '.join(MODELS)}"
        )
    if count < 1:
        raise StepError(
            "proteinmpnn_noise_robustness: num_seq_per_target must be at least 1"
        )
    if device not in {"cpu", "cuda"}:
        raise StepError(
            "proteinmpnn_noise_robustness: device must be 'cpu' or 'cuda'"
        )
    python = str(params.get("python_executable") or "") or sys.executable
    out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-noise-"))
    command = [
        python,
        str(runner),
        "--pdb_path",
        structure.as_posix(),
        "--out_folder",
        out_dir.as_posix(),
        "--num_seq_per_target",
        str(count),
        "--sampling_temp",
        temperature,
        "--seed",
        str(seed),
        "--suppress_print",
        "1",
        "--model_name",
        model_name,
    ]
    if weights is not None:
        command.extend(["--path_to_model_weights", weights.as_posix()])
    if chain:
        command.extend(["--pdb_path_chains", chain])
    environment = dict(os.environ)
    if device == "cpu":
        environment["CUDA_VISIBLE_DEVICES"] = ""
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
            raise StepError(
                "proteinmpnn_noise_robustness: the designer failed with exit "
                f"code {completed.returncode}: {' | '.join(tail)}"
            )
        fasta = out_dir / "seqs" / f"{structure.stem}.fa"
        if not fasta.is_file():
            raise StepError(
                "proteinmpnn_noise_robustness: the designer produced no FASTA at "
                f"{fasta}"
            )
        records = parse_design_fasta(fasta)
    except subprocess.TimeoutExpired as error:
        raise StepError(
            "proteinmpnn_noise_robustness: the designer timed out after "
            f"{timeout} s"
        ) from error
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    if not records:
        raise StepError(
            "proteinmpnn_noise_robustness: the designer produced no designs"
        )
    return records


class ProteinmpnnNoiseRobustnessStep(Step):
    """ProteinMPNN sequence recovery under increasing backbone noise."""

    provider = "operon-core"

    parameters_file = (
        "proteinmpnn_noise_robustness."
        "ProteinmpnnNoiseRobustnessStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_noise_robustness",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN noise robustness",
        "description": (
            "Perturb the backbone coordinates with increasing Gaussian noise, "
            "redesign every replicate with the official ProteinMPNN runner and "
            "report the mean sequence recovery and model scores per noise "
            "level as a measure of design robustness."
        ),
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
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        structure = Path(
            str(params.get("structure_path", "")).strip()
        ).expanduser()
        repo = Path(
            str(params.get("proteinmpnn_path", "")).strip()
            or os.environ.get("OPERON_PROTEINMPNN_PATH", "")
        ).expanduser()
        weights_text = str(params.get("weights_path", "")).strip()
        chain = str(params.get("chains", "")).strip()
        levels = parse_levels(str(params.get("noise_levels", "0,1,2")))
        replicates = int(params.get("replicates") or 1)
        timeout = float(params.get("timeout_seconds") or 1800.0)
        out_name = params.get("output", self.name)

        if not structure.is_file():
            raise StepError(
                f"proteinmpnn_noise_robustness: structure_path '{structure}' is "
                "not a file"
            )
        if structure.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "proteinmpnn_noise_robustness: structure_path must be a .pdb "
                "file"
            )
        if not repo.is_dir():
            raise StepError(
                f"proteinmpnn_noise_robustness: proteinmpnn_path '{repo}' is not "
                "a directory (set OPERON_PROTEINMPNN_PATH or the "
                "proteinmpnn_path parameter)"
            )
        runner = repo / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_noise_robustness: '{runner}' does not exist; point "
                "proteinmpnn_path at the official ProteinMPNN checkout"
            )
        weights = Path(weights_text).expanduser() if weights_text else (
            repo / "vanilla_model_weights"
        )
        if not weights.is_dir():
            raise StepError(
                "proteinmpnn_noise_robustness: weights directory "
                f"{weights} does not exist; set weights_path to the directory "
                "holding v_48_*.pt"
            )
        model_name = str(params.get("model_name") or "v_48_020")
        if model_name not in MODELS:
            raise StepError(
                "proteinmpnn_noise_robustness: model_name must be one of "
                f"{', '.join(MODELS)}"
            )
        if replicates < 1 or replicates > _MAX_REPLICATES:
            raise StepError(
                "proteinmpnn_noise_robustness: replicates must be between 1 and "
                f"{_MAX_REPLICATES}"
            )
        if not levels:
            raise StepError(
                "proteinmpnn_noise_robustness: noise_levels selects no level"
            )

        text = structure.read_text(encoding="utf-8", errors="replace")
        coordinates, lines = pdb_coordinates(text)
        seed = int(params.get("seed") or 0)
        rng = np.random.default_rng(seed)
        rows: list[tuple[float, ...]] = []
        with tempfile.TemporaryDirectory(prefix="operon-noise-") as folder:
            root = Path(folder)
            for sigma in levels:
                for replicate in range(replicates):
                    displaced = perturb_coordinates(coordinates, sigma, rng)
                    replica = root / f"noise_{sigma}_{replicate}.pdb"
                    replica.write_text(
                        write_perturbed(text, lines, displaced), encoding="utf-8"
                    )
                    records = run_replicate(
                        params, repo, runner, weights, replica, chain, timeout
                    )
                    rows.append(noise_row(records, sigma, replicate))

        labels = {
            "noise": {
                f"sigma{row[0]:g}:r{int(row[1])}": position
                for position, row in enumerate(rows)
            },
            "statistic": {
                name: position for position, name in enumerate(_STATISTICS)
            },
        }
        data = np.asarray(rows, dtype=np.float32)
        form_out = Form(
            data=data,
            dims=["noise", "statistic"],
            labels=labels,
            info={
                "structure_path": str(structure),
                "model_name": model_name,
                "noise_levels": list(levels),
                "replicates": replicates,
                "n_rows": len(rows),
            },
        )
        ctx[out_name] = form_out
        best = min(rows, key=lambda row: row[0])
        self._export_data = {
            "n_rows": len(rows),
            "noise_levels": list(levels),
            "replicates": replicates,
            "zero_sigma_recovery": float(best[5]) if best[0] == 0 else None,
        }
        print(
            f"[{self.name}] {len(levels)} noise levels x {replicates} "
            f"replicates -> {len(rows)} rows"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
