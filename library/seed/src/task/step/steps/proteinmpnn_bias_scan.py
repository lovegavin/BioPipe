"""Measure how an amino-acid sampling bias shifts per-position design frequencies."""

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
from src.task.context.base import Context
from src.task.step.base import Step

from ._esm_common import AA_ORDER
from .proteinmpnn_design import MODELS, parse_design_fasta

_AA_INDEX = {letter: index for index, letter in enumerate(AA_ORDER)}


def parse_bias(text: str) -> dict[str, float]:
    """Parse ``W:1.5,C:-0.5`` into an amino-acid bias dictionary."""

    bias: dict[str, float] = {}
    for token in str(text or "").replace(";", ",").split(","):
        piece = token.strip()
        if not piece:
            continue
        if ":" in piece:
            residue, value = piece.split(":", 1)
        elif "=" in piece:
            residue, value = piece.split("=", 1)
        else:
            raise StepError(
                "proteinmpnn_bias_scan: bias token "
                f"'{piece}' is not of the form C:-1.0"
            )
        residue = residue.strip().upper()
        if residue not in _AA_INDEX:
            raise StepError(
                "proteinmpnn_bias_scan: bias token "
                f"'{piece}' must name a single standard amino acid"
            )
        try:
            number = float(value)
        except ValueError:
            raise StepError(
                f"proteinmpnn_bias_scan: bias value '{value.strip()}' is not a number"
            )
        if not np.isfinite(number) or abs(number) > 10.0:
            raise StepError(
                "proteinmpnn_bias_scan: bias values must be finite and within [-10, 10]"
            )
        bias[residue] = float(number)
    if not bias:
        raise StepError("proteinmpnn_bias_scan: bias must name at least one amino acid")
    return bias


def frequency_matrix(designs: list[dict], length: int) -> np.ndarray:
    """Per-position amino-acid frequencies from parsed designs."""

    if not designs:
        raise StepError("proteinmpnn_bias_scan: at least one design is required")
    counts = np.zeros((length, len(AA_ORDER)), dtype=np.float64)
    for design in designs:
        sequence = str(design["sequence"]).replace("/", "")
        if len(sequence) != length:
            raise StepError(
                "proteinmpnn_bias_scan: design length "
                f"{len(sequence)} does not match the target length {length}"
            )
        for position, residue in enumerate(sequence):
            index = _AA_INDEX.get(residue.upper())
            if index is None:
                raise StepError(
                    "proteinmpnn_bias_scan: design contains the non-standard residue "
                    f"'{residue}' at position {position + 1}"
                )
            counts[position, index] += 1.0
    return counts / counts.sum(axis=1, keepdims=True)


def bias_shift(baseline: np.ndarray, biased: np.ndarray) -> np.ndarray:
    """Signed frequency shift induced by the sampling bias."""

    if baseline.shape != biased.shape:
        raise StepError(
            "proteinmpnn_bias_scan: baseline and biased frequency tables differ in shape"
        )
    shift = biased - baseline
    if not np.isfinite(shift).all():
        raise StepError("proteinmpnn_bias_scan: the shift table contains non-finite values")
    return shift.astype(np.float32)


def run_designer(
    *,
    repo: Path,
    structure: Path,
    out_dir: Path,
    python: str,
    count: int,
    temperature: float,
    seed: int,
    model_name: str,
    weights: str,
    chains: str,
    device: str,
    timeout: int,
    bias_path: Path | None,
) -> list[dict]:
    """Run the official ProteinMPNN sampler once and parse the generated designs."""

    runner = repo / "protein_mpnn_run.py"
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
        str(temperature),
        "--seed",
        str(seed),
        "--model_name",
        model_name,
        "--batch_size",
        "1",
        "--suppress_print",
        "1",
    ]
    if weights:
        command += ["--path_to_model_weights", Path(weights).expanduser().as_posix()]
    if chains:
        command += ["--pdb_path_chains", chains]
    if bias_path is not None:
        command += ["--bias_AA_jsonl", bias_path.as_posix()]
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = "" if device == "cpu" else env.get(
        "CUDA_VISIBLE_DEVICES", "0"
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
            f"proteinmpnn_bias_scan: the designer timed out after {timeout} s"
        )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-800:]
        raise StepError(
            "proteinmpnn_bias_scan: the designer failed with exit code "
            f"{completed.returncode}: {tail}"
        )
    fasta = out_dir / "seqs" / f"{structure.stem}.fa"
    if not fasta.is_file():
        raise StepError(
            f"proteinmpnn_bias_scan: the designer produced no FASTA at {fasta}"
        )
    designs = parse_design_fasta(fasta)
    if not designs:
        raise StepError(
            "proteinmpnn_bias_scan: the designer FASTA has no generated designs"
        )
    return designs


class ProteinmpnnBiasScanStep(Step):
    """Quantify the per-position effect of a ProteinMPNN amino-acid bias."""

    provider = "operon-core"
    parameters_file = "proteinmpnn_bias_scan.ProteinmpnnBiasScanStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_bias_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN Bias Scan",
        "description": (
            "Sample designs with and without an amino-acid bias using the official "
            "ProteinMPNN runner and report the per-position frequency shift induced by "
            "the bias."
        ),
        "category": "Machine Learning",
        "icon": "Shuffle",
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
        repo_value = str(params.get("proteinmpnn_path", "") or "")
        repo = Path(repo_value).expanduser() if repo_value else Path(os.environ.get("OPERON_PROTEINMPNN_PATH", ""))
        weights = str(params.get("weights_path", "") or "")
        python = str(params.get("python_executable", "") or "") or sys.executable
        model_name = str(params.get("model_name", "v_48_020") or "v_48_020")
        chains = str(params.get("chains", "") or "").strip()
        position_dim = str(params.get("position_dim", "position"))
        aa_dim = str(params.get("amino_acid_dim", "amino_acid"))
        bias_text = params.get("bias", "")
        raw_count = params.get("num_seq_per_target", 32)
        count = 32 if raw_count is None else int(raw_count)
        raw_temperature = params.get("temperature", 0.5)
        temperature = 0.5 if raw_temperature is None else float(raw_temperature)
        raw_seed = params.get("seed", 1)
        seed = 1 if raw_seed is None else int(raw_seed)
        device = str(params.get("device", "cpu") or "cpu").strip().lower()
        raw_timeout = params.get("timeout", 1800)
        timeout = 1800 if raw_timeout is None else int(raw_timeout)
        out_name = str(params.get("output", "shift") or "shift")
        if not structure.is_file():
            raise StepError(
                "proteinmpnn_bias_scan: structure_path must point at a PDB file, "
                f"got '{structure}'"
            )
        if model_name not in MODELS:
            raise StepError(
                f"proteinmpnn_bias_scan: model_name must be one of {list(MODELS)}"
            )
        if not repo_value and not os.environ.get("OPERON_PROTEINMPNN_PATH"):
            raise StepError(
                "proteinmpnn_bias_scan: proteinmpnn_path is required; point it at an "
                "official ProteinMPNN checkout"
            )
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                f"proteinmpnn_bias_scan: {repo / 'protein_mpnn_run.py'} does not exist"
            )
        if count < 2 or count > 500:
            raise StepError("proteinmpnn_bias_scan: num_seq_per_target must be in [2, 500]")
        if temperature <= 0 or temperature > 5:
            raise StepError("proteinmpnn_bias_scan: temperature must be in (0, 5]")
        if seed < 0:
            raise StepError("proteinmpnn_bias_scan: seed must not be negative")
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_bias_scan: device must be 'cpu' or 'cuda'")
        bias = parse_bias(str(bias_text))
        baseline_dir = Path(tempfile.mkdtemp(prefix="operon-bias-base-"))
        biased_dir = Path(tempfile.mkdtemp(prefix="operon-bias-boost-"))
        try:
            bias_file = biased_dir / "bias.json"
            bias_file.write_text(json.dumps(bias), encoding="utf-8")
            baseline = run_designer(
                repo=repo,
                structure=structure,
                out_dir=baseline_dir,
                python=python,
                count=count,
                temperature=temperature,
                seed=seed,
                model_name=model_name,
                weights=weights,
                chains=chains,
                device=device,
                timeout=timeout,
                bias_path=None,
            )
            biased = run_designer(
                repo=repo,
                structure=structure,
                out_dir=biased_dir,
                python=python,
                count=count,
                temperature=temperature,
                seed=seed,
                model_name=model_name,
                weights=weights,
                chains=chains,
                device=device,
                timeout=timeout,
                bias_path=bias_file,
            )
        finally:
            shutil.rmtree(baseline_dir, ignore_errors=True)
            shutil.rmtree(biased_dir, ignore_errors=True)
        length = len(str(baseline[0]["sequence"]).replace("/", ""))
        baseline_freq = frequency_matrix(baseline, length)
        biased_freq = frequency_matrix(biased, length)
        shift = bias_shift(baseline_freq, biased_freq)
        top: list[dict] = []
        for position in range(length):
            index = int(np.argmax(np.abs(shift[position])))
            top.append(
                {
                    "position": position + 1,
                    "amino_acid": AA_ORDER[index],
                    "delta": round(float(shift[position, index]), 6),
                }
            )
        out = Form(
            data=shift,
            dims=[position_dim, aa_dim],
            labels={
                position_dim: {str(index + 1): index for index in range(length)},
                aa_dim: {letter: index for index, letter in enumerate(AA_ORDER)},
            },
            info={
                "missing_code": np.nan,
                "structure_path": str(structure),
                "bias": bias,
                "model_name": model_name,
                "chains": chains,
                "num_seq_per_target": count,
                "temperature": temperature,
                "seed": seed,
                "device": device,
                "n_baseline": len(baseline),
                "n_biased": len(biased),
                "aa_order": AA_ORDER,
                "mean_abs_shift": float(np.abs(shift).mean()),
                "top_changes": top,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_baseline": len(baseline),
            "n_biased": len(biased),
            "bias": bias,
            "mean_abs_shift": round(float(np.abs(shift).mean()), 6),
            "max_shift": round(float(np.abs(shift).max()), 6),
            "top_changes": top[:10],
        }
        print(
            f"[proteinmpnn_bias_scan] {length} positions, bias {bias}, "
            f"mean |shift| {float(np.abs(shift).mean()):.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
