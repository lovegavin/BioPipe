"""ProteinMPNN per-position perplexity from conditional probabilities."""

from __future__ import annotations

import re
import shutil
import sys
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
TOKEN_ALPHABET = AA_ORDER + "X"
MODELS = ("v_48_002", "v_48_010", "v_48_020", "v_48_030")
_NUMBER = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$|^[+-]?(?:nan|inf)$",
    re.IGNORECASE,
)
_FIELDS = ("perplexity", "entropy_bits", "most_likely_prob")
_STATISTICS = ("perplexity", "entropy_bits", "most_likely_prob")


def parse_native(path: Path) -> str:
    """Read the first sequence of a ProteinMPNN FASTA file."""
    if not path.is_file():
        raise StepError("proteinmpnn_perplexity: the native FASTA '{}' is missing".format(path))
    sequence: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith(">"):
            if sequence:
                return "".join(sequence).replace("/", "")
            continue
        sequence.append(text)
    if not sequence:
        raise StepError("proteinmpnn_perplexity: the native FASTA '{}' has no sequence".format(path))
    return "".join(sequence).replace("/", "")


def native_from_tokens(payload, length: int) -> str:
    """Recover the native sequence from the token indices stored by the runner."""
    if "S" not in payload:
        raise StepError("proteinmpnn_perplexity: the probability file has no S token array")
    tokens = np.asarray(payload["S"]).reshape(-1)
    if tokens.shape[0] < length:
        raise StepError(
            "proteinmpnn_perplexity: the token array has {} entries, fewer than the {} residues".format(
                tokens.shape[0], length
            )
        )
    letters = []
    for token in tokens[:length]:
        index = int(token)
        if index < 0 or index >= len(TOKEN_ALPHABET):
            raise StepError(
                "proteinmpnn_perplexity: token {} is outside the ProteinMPNN alphabet".format(index)
            )
        letters.append(TOKEN_ALPHABET[index])
    return "".join(letters)


def probability_matrix(payload, length: int) -> np.ndarray:
    """Extract a (length, 20) probability matrix from a conditional-probs payload."""
    if "log_p" not in payload:
        raise StepError("proteinmpnn_perplexity: the probability file has no 'log_p' array")
    log_p = np.asarray(payload["log_p"], dtype=np.float64)
    if log_p.ndim != 3:
        raise StepError(
            "proteinmpnn_perplexity: 'log_p' must be three-dimensional, got shape {}".format(log_p.shape)
        )
    probabilities = np.exp(log_p[0])
    if probabilities.shape[1] == 21:
        probabilities = probabilities[:, :20]
    if probabilities.shape[0] == length + 1:
        probabilities = probabilities[:length]
    if probabilities.shape[0] != length or probabilities.shape[1] != 20:
        raise StepError(
            "proteinmpnn_perplexity: expected a ({} , 20) probability matrix, got {}".format(
                length, probabilities.shape
            )
        )
    totals = probabilities.sum(axis=1, keepdims=True)
    if np.any(~np.isfinite(totals)) or np.any(totals <= 0.0):
        raise StepError("proteinmpnn_perplexity: the probability matrix has an empty or invalid row")
    return probabilities / totals


def perplexity_rows(probabilities: np.ndarray) -> list[tuple[float, float, float]]:
    """Return per-position (perplexity, entropy_bits, most likely probability)."""
    clipped = np.clip(probabilities, 1e-12, None)
    entropy_nat = -np.sum(probabilities * np.log(clipped), axis=1)
    if np.any(~np.isfinite(entropy_nat)):
        raise StepError("proteinmpnn_perplexity: the entropy computation produced non-finite values")
    return [
        (float(np.exp(value)), float(value / np.log(2.0)), float(row.max()))
        for row, value in zip(probabilities, entropy_nat)
    ]


def most_likely(probabilities: np.ndarray) -> str:
    """Return the most likely amino acid at every position."""
    return "".join(AA_ORDER[index] for index in probabilities.argmax(axis=1))


def designer_command(
    params: dict,
    structure: Path,
    out_dir: Path,
    weights: Path | None,
    fasta: Path,
) -> list[str]:
    """Build the official ProteinMPNN conditional-probability command."""
    python = str(params.get("python_executable") or "") or sys.executable
    command = [
        python,
        "protein_mpnn_run.py",
        "--pdb_path",
        structure.as_posix(),
        "--out_folder",
        out_dir.as_posix(),
        "--num_seq_per_target",
        str(int(params.get("num_seq_per_target", 8))),
        "--batch_size",
        "1",
        "--seed",
        str(int(params.get("seed", 1))),
        "--model_name",
        str(params.get("model_name", "v_48_020")),
        "--conditional_probs_only",
        "1",
        "--suppress_print",
        "1",
    ]
    if weights is not None:
        command.extend(["--path_to_model_weights", weights.as_posix()])
    chains = str(params.get("chains", "") or "").strip()
    if chains:
        command.extend(["--pdb_path_chains", chains])
    return command


def run_designer(params: dict, structure: Path, weights: Path | None) -> tuple[str, np.ndarray]:
    """Run the official runner and return (native sequence, probability matrix)."""
    repo = Path(str(params.get("proteinmpnn_path", ""))).resolve()
    if not repo.is_dir():
        raise StepError("proteinmpnn_perplexity: proteinmpnn_path '{}' is not a directory".format(repo))
    runner = repo / "protein_mpnn_run.py"
    if not runner.is_file():
        raise StepError("proteinmpnn_perplexity: the repository has no protein_mpnn_run.py at '{}'".format(repo))
    timeout = int(params.get("timeout", 1800))
    out_dir = Path(tempfile.mkdtemp(prefix="operon-mpnn-perplexity-"))
    try:
        fasta = out_dir / "native.fa"
        command = designer_command(params, structure, out_dir, weights, fasta)
        env = dict()
        import os

        env.update(os.environ)
        if str(params.get("device", "cpu")) != "cuda":
            env["CUDA_VISIBLE_DEVICES"] = ""
        try:
            completed = subprocess.run(
                command,
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as error:
            raise StepError(
                "proteinmpnn_perplexity: the designer timed out after {} s".format(timeout)
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            message = tail[-1] if tail else "no output"
            raise StepError(
                "proteinmpnn_perplexity: the designer failed with exit code {}: {}".format(
                    completed.returncode, message
                )
            )
        payload_path = out_dir / "conditional_probs_only" / "{}.npz".format(structure.stem)
        if not payload_path.is_file():
            raise StepError(
                "proteinmpnn_perplexity: the designer wrote no conditional-probability file at '{}'".format(
                    payload_path
                )
            )
        payload = np.load(payload_path, allow_pickle=True)
        log_p = np.asarray(payload["log_p"])
        length = int(log_p.shape[1])
        native = native_from_tokens(payload, length)
        probabilities = probability_matrix(payload, length)
        return native, probabilities
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


class ProteinmpnnPerplexityStep(Step):
    """Per-position ProteinMPNN perplexity from conditional amino-acid probabilities."""

    provider = "operon-core"
    parameters_file = "proteinmpnn_perplexity.ProteinmpnnPerplexityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_perplexity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN Perplexity",
        "description": (
            "Computes how uncertain ProteinMPNN is at every designed position. The operator "
            "runs the official conditional-probability pass and reports the effective number of "
            "amino-acid choices, the position entropy and the most likely probability."
        ),
        "category": "Machine Learning",
        "icon": "ArrowsDownUp",
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
        "resources": {"memory_modes": ["full"], "supports_cuda": True, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 0,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (64 * 1024 * 1024, 0)

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        structure = Path(str(params.get("structure_path", ""))).expanduser()
        if not structure.is_file():
            raise StepError(
                "proteinmpnn_perplexity: structure_path '{}' is not a file".format(structure)
            )
        repository = Path(str(params.get("proteinmpnn_path", ""))).expanduser()
        if not repository.is_dir():
            raise StepError(
                "proteinmpnn_perplexity: proteinmpnn_path '{}' is not a directory".format(repository)
            )
        model = str(params.get("model_name", "v_48_020"))
        if model not in MODELS:
            raise StepError(
                "proteinmpnn_perplexity: model_name must be one of {}, got '{}'".format(list(MODELS), model)
            )
        count = int(params.get("num_seq_per_target", 8))
        if count < 1:
            raise StepError("proteinmpnn_perplexity: num_seq_per_target must be at least 1")
        seed = int(params.get("seed", 1))
        if seed < 0:
            raise StepError("proteinmpnn_perplexity: seed must not be negative")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_perplexity: device must be 'cpu' or 'cuda'")
        weights_text = str(params.get("weights_path", "") or "").strip()
        weights = None
        if weights_text:
            weights = Path(weights_text).expanduser().resolve()
            if not weights.exists():
                raise StepError(
                    "proteinmpnn_perplexity: weights_path '{}' does not exist".format(weights)
                )
        position_dim = str(params.get("position_dim", "position"))
        native, probabilities = run_designer(params, structure.resolve(), weights)
        rows = perplexity_rows(probabilities)
        labels = {str(index + 1): index for index in range(len(rows))}
        data = np.asarray(rows, dtype=np.float32)
        output = Form(
            data=data,
            dims=[position_dim, "statistic"],
            labels={position_dim: labels, "statistic": {name: index for index, name in enumerate(_STATISTICS)}},
            info={
                "missing_code": np.nan,
                "structure_path": str(structure),
                "model_name": model,
                "chains": str(params.get("chains", "") or ""),
                "native_sequence": native,
                "most_likely": most_likely(probabilities),
                "mean_perplexity": float(data[:, 0].mean()) if len(data) else 0.0,
                "num_positions": len(rows),
                "AA_ORDER": AA_ORDER,
            },
            axis_info={},
        )
        output.validate()
        output_name = str(params.get("output", "perplexity"))
        ctx[output_name] = output
        self._export_data = {
            "structure_path": str(structure),
            "model_name": model,
            "num_positions": len(rows),
            "mean_perplexity": float(data[:, 0].mean()) if len(data) else 0.0,
            "native_sequence": native,
            "most_likely": output.info["most_likely"],
        }
        print(
            "[proteinmpnn_perplexity] {} positions, mean perplexity {:.3f}".format(
                len(rows), output.info["mean_perplexity"]
            )
        )

    def export(self, ctx) -> dict:
        return dict(getattr(self, "_export_data", {}))
