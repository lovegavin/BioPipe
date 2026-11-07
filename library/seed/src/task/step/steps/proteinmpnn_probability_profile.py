"""Per-position amino-acid probabilities from ProteinMPNN conditional-probability mode."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps.proteinmpnn_score import MODELS

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
STATISTICS = ("probability",)


def probabilities(npz: Path, n_amino_acids: int = 20) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return per-position probabilities, the native S codes, mask and design mask."""

    with np.load(npz, allow_pickle=True) as archive:
        log_p = np.asarray(archive["log_p"], dtype=np.float64)
        native = np.asarray(archive["S"], dtype=np.int64).ravel()
        mask = np.asarray(archive["mask"], dtype=np.float64).ravel()
        design = np.asarray(archive["design_mask"], dtype=np.float64).ravel()
    if log_p.ndim != 3:
        raise StepError(
            "proteinmpnn_probability_profile: the conditional-probability file has "
            f"log_p shape {log_p.shape}, expected (batches, positions, alphabet)"
        )
    if log_p.shape[2] < n_amino_acids:
        raise StepError(
            "proteinmpnn_probability_profile: the probability array has fewer than "
            f"{n_amino_acids} alphabet columns ({log_p.shape[2]})"
        )
    if log_p.shape[1] != native.size:
        raise StepError(
            "proteinmpnn_probability_profile: log_p positions and native residue "
            f"counts disagree ({log_p.shape[1]} vs {native.size})"
        )
    with np.errstate(over="ignore"):
        values = np.exp(log_p[:, :, :n_amino_acids])
    mean = values.mean(axis=0)
    return mean, native, mask, design


def native_codes_to_sequence(codes: np.ndarray) -> str:
    """Decode ProteinMPNN native residue codes into a one-letter sequence."""

    letters = []
    for code in codes:
        index = int(code)
        if 0 <= index < len(AA_ORDER):
            letters.append(AA_ORDER[index])
        else:
            letters.append("X")
    return "".join(letters)


class ProteinmpnnProbabilityProfileStep(Step):
    provider = 'operon-core'
    """Per-position amino-acid preference profile from ProteinMPNN."""


    parameters_file = "proteinmpnn_probability_profile.ProteinmpnnProbabilityProfileStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_probability_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN probability profile",
        "description": (
            "Run the official ProteinMPNN runner in --conditional_probs_only mode and report "
            "the per-position amino-acid probability profile p(s_i | backbone, rest of sequence)."
        ),
        "category": "Machine Learning",
        "icon": "ChartLine",
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
        structure_path = Path(
            str(params.get("structure_path", "") or "").strip()
        ).expanduser()
        proteinmpnn_path = Path(
            str(params.get("proteinmpnn_path", "") or "").strip()
            or os.environ.get("OPERON_PROTEINMPNN_PATH", "")
        ).expanduser()
        weights_text = str(params.get("weights_path", "") or "").strip()
        python_executable = str(params.get("python_executable", "") or "").strip()
        model_name = str(params.get("model_name", "v_48_020") or "v_48_020").strip()
        chains = str(params.get("chains", "") or "").strip()
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        num_batches = int(params.get("num_batches", 1))
        seed = int(params.get("seed", 1))
        timeout = float(params.get("timeout_seconds", 1800.0))
        out_name = params.get("output", self.name)

        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_probability_profile: structure_path '{structure_path}' is not a file"
            )
        if structure_path.suffix.lower() not in (".pdb", ".ent"):
            raise StepError(
                "proteinmpnn_probability_profile: structure_path must be a .pdb file "
                "(ProteinMPNN needs atom names)"
            )
        if not proteinmpnn_path.is_dir():
            raise StepError(
                f"proteinmpnn_probability_profile: proteinmpnn_path '{proteinmpnn_path}' is not "
                "a directory (set OPERON_PROTEINMPNN_PATH or the proteinmpnn_path parameter)"
            )
        runner = proteinmpnn_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_probability_profile: '{runner}' does not exist; point "
                "proteinmpnn_path at the official ProteinMPNN checkout"
            )
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_probability_profile: model_name must be one of {list(MODELS)}"
            )
        if device not in ("cpu", "cuda"):
            raise StepError(
                "proteinmpnn_probability_profile: device must be 'cpu' or 'cuda'"
            )
        if not 1 <= num_batches <= 8:
            raise StepError(
                "proteinmpnn_probability_profile: num_batches must be between 1 and 8"
            )
        weights_path = (
            Path(weights_text).expanduser()
            if weights_text
            else proteinmpnn_path / "vanilla_model_weights"
        )
        weight_file = weights_path / f"{model_name}.pt"
        if not weight_file.is_file():
            raise StepError(
                f"proteinmpnn_probability_profile: weights '{weight_file}' not found; set "
                "weights_path to the directory holding v_48_*.pt"
            )

        out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-probs-"))
        started = time.monotonic()
        try:
            command = [
                python_executable or sys.executable,
                runner.as_posix(),
                "--pdb_path",
                structure_path.as_posix(),
                "--out_folder",
                out_dir.as_posix(),
                "--conditional_probs_only",
                "1",
                "--num_seq_per_target",
                str(num_batches),
                "--batch_size",
                "1",
                "--seed",
                str(seed),
                "--path_to_model_weights",
                weights_path.as_posix(),
                "--model_name",
                model_name,
                "--suppress_print",
                "1",
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
                cwd=str(proteinmpnn_path),
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "").strip()
                raise StepError(
                    "proteinmpnn_probability_profile: protein_mpnn_run.py failed with exit "
                    f"code {completed.returncode}: {tail[-800:]}"
                )
            folder = out_dir / "conditional_probs_only"
            candidates = sorted(folder.glob(f"{structure_path.stem}*"))
            if not candidates:
                raise StepError(
                    "proteinmpnn_probability_profile: the runner produced no "
                    f"conditional-probability file in '{folder}'; stdout tail: "
                    f"{(completed.stdout or '').strip()[-400:]}"
                )
            row_prob, native, mask, design = probabilities(candidates[0])
            elapsed = time.monotonic() - started
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

        keep = mask > 0.5
        positions = np.flatnonzero(keep)
        if positions.size == 0:
            raise StepError(
                "proteinmpnn_probability_profile: the runner produced no scored position"
            )
        probs = row_prob[positions]
        logs = np.log(probs, out=np.zeros_like(probs), where=probs > 0)
        entropy = -np.sum(probs * logs, axis=1)
        best = np.argmax(probs, axis=1)
        native_sequence = native_codes_to_sequence(native)
        labels = {
            "position": {str(int(index) + 1): position for position, index in enumerate(positions)},
            "amino_acid": {letter: index for index, letter in enumerate(AA_ORDER)},
        }
        info = {
            "missing_code": np.nan,
            "structure_path": str(structure_path),
            "model_name": model_name,
            "chains": chains or "all",
            "device": device,
            "num_batches": num_batches,
            "elapsed_seconds": round(elapsed, 3),
            "native_sequence": native_sequence,
            "n_positions": int(positions.size),
            "positions": [int(index) + 1 for index in positions],
            "design_mask": [float(design[index]) for index in positions],
            "most_likely": [AA_ORDER[int(index)] for index in best],
            "entropy": [round(float(value), 6) for value in entropy],
            "metric": "conditional_probability",
        }
        out = Form(
            data=np.asarray(probs, dtype=np.float32),
            dims=["position", "amino_acid"],
            labels=labels,
            info=info,
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_positions": int(positions.size),
            "native_sequence": native_sequence,
            "model_name": model_name,
            "device": device,
            "elapsed_seconds": round(elapsed, 3),
            "most_likely": info["most_likely"],
            "mean_entropy": round(float(entropy.mean()), 6),
        }
        print(
            f"[proteinmpnn_probability_profile] {positions.size} positions from "
            f"{structure_path.name} ({model_name}, {device}, {elapsed:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


__all__ = [
    "AA_ORDER",
    "ProteinmpnnProbabilityProfileStep",
    "native_codes_to_sequence",
    "probabilities",
]
