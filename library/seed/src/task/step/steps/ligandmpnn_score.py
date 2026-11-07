"""Per-residue sequence likelihoods from the official LigandMPNN scorer."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from src.core.forms.form import Form
from src.task.context.base import Context
from src.core.errors import StepError
from src.task.step.base import Step

_MODEL_TYPES = ("ligand_mpnn", "protein_mpnn", "soluble_mpnn")
_CHECKPOINT_FLAG = {
    "ligand_mpnn": "--checkpoint_ligand_mpnn",
    "protein_mpnn": "--checkpoint_protein_mpnn",
    "soluble_mpnn": "--checkpoint_soluble_mpnn",
}
_STATISTICS = ("mean_log_prob", "std_log_prob")


def _repo_path(value: str) -> Path:
    text = value or os.environ.get("OPERON_LIGANDMPNN_PATH", "")
    if not text:
        raise StepError(
            "ligandmpnn_score: ligandmpnn_path is required; point it at a LigandMPNN checkout "
            "or set OPERON_LIGANDMPNN_PATH"
        )
    return Path(text).expanduser()


def _python(value: str) -> str:
    return value or shutil.which("python3") or "python"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - torch is optional
        return False


_RESIDUE_LABEL = re.compile(r"^([A-Za-z]*)(\d+)(.*)$")


def label_order(label: str) -> tuple:
    """Sort residue labels by chain, residue number and insertion code."""

    match = _RESIDUE_LABEL.match(str(label).strip())
    if match is None:
        return (str(label).strip(), 0, "", str(label))
    chain, number, suffix = match.groups()
    return (chain, int(number), suffix, str(label))


def _residue_labels(names, mask) -> list[str]:
    labels = []
    for index in range(len(mask)):
        value = names.get(index, names.get(str(index), f"residue{index + 1}")) if isinstance(names, dict) else f"residue{index + 1}"
        labels.append(str(value))
    return labels


def score_statistics(payload: dict) -> tuple[np.ndarray, list[str]]:
    """Collapse a LigandMPNN score payload into per-residue mean/std log-probabilities."""
    for key in ("log_probs", "native_sequence", "mask", "residue_names"):
        if key not in payload:
            raise StepError(f"ligandmpnn_score: the score payload has no '{key}' entry")
    log_probs = np.asarray(payload["log_probs"], dtype=np.float64)
    native = np.asarray(payload["native_sequence"], dtype=np.int64)
    mask = np.asarray(payload["mask"], dtype=np.float64)
    if log_probs.ndim != 3 or log_probs.shape[1] != native.shape[0]:
        raise StepError("ligandmpnn_score: the score payload has an unexpected shape")
    keep = np.flatnonzero(mask > 0)
    if keep.size == 0:
        raise StepError("ligandmpnn_score: the score payload has no scored residues")
    labels = _residue_labels(payload["residue_names"], mask)
    sequence = np.arange(log_probs.shape[0])[:, None]
    residues = np.arange(native.shape[0])[None, :]
    native_log_probs = log_probs[sequence, residues, native[None, :]]
    mean = native_log_probs.mean(axis=0)[keep]
    std = native_log_probs.std(axis=0)[keep]
    return np.stack([mean, std], axis=1), [labels[index] for index in keep]


class LigandMpnnScoreStep(Step):
    provider = "operon-core"
    parameters_file = "ligandmpnn_score.LigandMpnnScoreStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "ligandmpnn_score",
        "kind": "operator",
        "version": "1.0.0",
        "title": "LigandMPNN Score",
        "description": (
            "Score every residue of a structure against the native sequence with the "
            "official LigandMPNN scorer and report the mean and spread of the "
            "per-residue log-probabilities across scoring batches."
        ),
        "category": "Machine Learning",
        "icon": "TrendUp",
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
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs: list[Form]) -> None:
        params = ctx.step_params
        structure_text = str(params.get("structure_path", "")).strip()
        if not structure_text:
            raise StepError("ligandmpnn_score: structure_path is required")
        structure = Path(structure_text).expanduser()
        if not structure.is_file():
            raise StepError(f"ligandmpnn_score: structure_path '{structure}' is not a file")
        repo = _repo_path(str(params.get("ligandmpnn_path", "")))
        scorer = repo / "score.py"
        if not scorer.is_file():
            raise StepError(f"ligandmpnn_score: '{scorer}' does not look like a LigandMPNN checkout")
        weights_text = str(params.get("weights_path", "")).strip()
        if not weights_text:
            raise StepError("ligandmpnn_score: weights_path is required")
        weights = Path(weights_text).expanduser()
        if not weights.is_file():
            raise StepError(f"ligandmpnn_score: weights_path '{weights}' is not a file")

        model_type = str(params.get("model_type", "ligand_mpnn"))
        if model_type not in _MODEL_TYPES:
            raise StepError(f"ligandmpnn_score: model_type must be one of {list(_MODEL_TYPES)}")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("ligandmpnn_score: device must be 'cpu' or 'cuda'")
        if device == "cuda" and not _cuda_available():
            raise StepError("ligandmpnn_score: device 'cuda' was requested but CUDA is not available")
        number_of_batches = int(params.get("number_of_batches", 1))
        if number_of_batches < 1:
            raise StepError("ligandmpnn_score: number_of_batches must be at least 1")
        batch_size = int(params.get("batch_size", 1))
        if not 1 <= batch_size <= 64:
            raise StepError("ligandmpnn_score: batch_size must be between 1 and 64")
        seed = int(params.get("seed", 1))
        if seed < 0 or seed > 2**31 - 1:
            raise StepError("ligandmpnn_score: seed must be between 0 and 2147483647")
        cutoff = float(params.get("ligand_mpnn_cutoff_for_score", 8.0))
        if not 0.0 < cutoff <= 20.0:
            raise StepError("ligandmpnn_score: ligand_mpnn_cutoff_for_score must be in (0, 20]")
        timeout = int(params.get("timeout_seconds", 3600))
        if timeout < 1:
            raise StepError("ligandmpnn_score: timeout_seconds must be positive")
        use_sequence = bool(params.get("use_sequence", True))
        chains = str(params.get("chains_to_design", "")).replace(" ", "")
        output = str(params.get("output", "output"))

        out_dir = Path(tempfile.mkdtemp(prefix="operon-ligandmpnn-score-"))
        environment = dict(os.environ)
        if device == "cpu":
            environment["CUDA_VISIBLE_DEVICES"] = ""
        command = [
            _python(str(params.get("python_executable", ""))),
            scorer.name,
            "--pdb_path",
            structure.as_posix(),
            "--out_folder",
            out_dir.as_posix(),
            "--model_type",
            model_type,
            _CHECKPOINT_FLAG[model_type],
            weights.as_posix(),
            "--seed",
            str(seed),
            "--number_of_batches",
            str(number_of_batches),
            "--batch_size",
            str(batch_size),
            "--use_sequence",
            "1" if use_sequence else "0",
            "--autoregressive_score",
            "1",
            "--single_aa_score",
            "0",
            "--ligand_mpnn_use_atom_context",
            "1" if bool(params.get("ligand_mpnn_use_atom_context", True)) else "0",
            "--ligand_mpnn_use_side_chain_context",
            "1" if bool(params.get("ligand_mpnn_use_side_chain_context", False)) else "0",
            "--ligand_mpnn_cutoff_for_score",
            str(cutoff),
        ]
        if chains:
            command += ["--chains_to_design", chains]

        try:
            completed = subprocess.run(
                command,
                cwd=str(repo),
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise StepError(f"ligandmpnn_score: the scorer timed out after {timeout} seconds") from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
            detail = " | ".join(tail) if tail else "no scorer output"
            raise StepError(f"ligandmpnn_score: the scorer failed with exit code {completed.returncode}: {detail}")

        stats_path = out_dir / f"{structure.stem}.pt"
        try:
            if not stats_path.is_file():
                raise StepError(f"ligandmpnn_score: the scorer produced no statistics file at {stats_path}")
            import torch

            payload = torch.load(stats_path, map_location="cpu", weights_only=False)
            data, labels = score_statistics(payload)
            sequence = "".join(str(char) for char in payload.get("sequence", []))
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

        order = sorted(range(len(labels)), key=lambda index: label_order(labels[index]))
        data = data[order]
        labels = [labels[index] for index in order]
        out = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=["residue", "statistic"],
            labels={
                "residue": {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequence": sequence,
                "n_residues": len(labels),
                "total_log_prob": float(data[:, 0].sum()),
                "mean_log_prob": float(data[:, 0].mean()),
                "structure_path": str(structure),
                "model_type": model_type,
                "use_sequence": use_sequence,
                "number_of_batches": number_of_batches,
                "batch_size": batch_size,
                "metric": "mean log-probability of the native residue, higher is better",
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "residues": len(labels),
            "total_log_prob": out.info["total_log_prob"],
            "mean_log_prob": out.info["mean_log_prob"],
            "sequence": sequence,
            "structure_path": str(structure),
        }
        print(
            f"ligandmpnn_score: {len(labels)} residues, mean log-probability "
            f"{out.info['mean_log_prob']:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
