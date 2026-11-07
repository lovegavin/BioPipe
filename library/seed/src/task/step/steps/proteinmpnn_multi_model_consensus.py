"""Consensus design across several ProteinMPNN checkpoints."""

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

AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"


def parse_models(text: str) -> list[str]:
    """Return the deduplicated checkpoint names requested by ``text``."""
    names = [
        piece.strip()
        for piece in str(text).replace(";", ",").split(",")
        if piece.strip()
    ]
    if not names:
        raise StepError(
            "proteinmpnn_multi_model_consensus: models must name at least one checkpoint"
        )
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        if name not in MODELS:
            raise StepError(
                "proteinmpnn_multi_model_consensus: model "
                f"'{name}' is unknown; use one of {list(MODELS)}"
            )
        if name in seen:
            raise StepError(
                "proteinmpnn_multi_model_consensus: model "
                f"'{name}' is listed twice"
            )
        seen.add(name)
        ordered.append(name)
    return ordered


def position_frequencies(sequences: list[str], length: int) -> np.ndarray:
    """Count each amino acid at every position over ``sequences``."""
    if not sequences:
        raise StepError(
            "proteinmpnn_multi_model_consensus: at least one design is required"
        )
    counts = np.zeros((length, len(AA_ORDER)), dtype=np.float32)
    index = {aa: position for position, aa in enumerate(AA_ORDER)}
    for sequence in sequences:
        if len(sequence) != length:
            raise StepError(
                "proteinmpnn_multi_model_consensus: design length "
                f"{len(sequence)} does not match the backbone length {length}"
            )
        for position, residue in enumerate(sequence):
            column = index.get(residue)
            if column is None:
                raise StepError(
                    "proteinmpnn_multi_model_consensus: design contains the "
                    f"non-standard residue '{residue}' at position {position + 1}"
                )
            counts[position, column] += 1.0
    total = counts.sum(axis=1, keepdims=True)
    if np.any(total == 0):
        raise StepError(
            "proteinmpnn_multi_model_consensus: a position has no design counts"
        )
    return counts / total


def consensus_sequence(frequencies: np.ndarray) -> str:
    """Return the most frequent amino acid at every position."""
    return "".join(AA_ORDER[int(index)] for index in frequencies.argmax(axis=1))


class ProteinmpnnMultiModelConsensusStep(Step):
    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_multi_model_consensus"
        ".ProteinmpnnMultiModelConsensusStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_multi_model_consensus",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN 多模型共识",
        "description": "用多个 ProteinMPNN checkpoint 采样并汇总逐位点共识频率。",
        "category": "Machine Learning",
        "icon": "Stack",
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
                "proteinmpnn_multi_model_consensus: structure_path is required; point "
                "it at a PDB file"
            )
        structure_path = Path(structure)
        if not structure_path.is_file():
            raise StepError(
                f"proteinmpnn_multi_model_consensus: structure_path '{structure}' is "
                "not a file"
            )
        repo = str(params.get("proteinmpnn_path", "")).strip()
        if not repo:
            repo = os.environ.get("OPERON_PROTEINMPNN_PATH", "").strip()
        if not repo:
            raise StepError(
                "proteinmpnn_multi_model_consensus: proteinmpnn_path is required; "
                "point it at the official ProteinMPNN checkout"
            )
        repo_path = Path(repo)
        runner = repo_path / "protein_mpnn_run.py"
        if not runner.is_file():
            raise StepError(
                f"proteinmpnn_multi_model_consensus: '{repo}' must contain "
                "protein_mpnn_run.py"
            )
        weights_text = str(params.get("weights_path", "")).strip()
        weights_path = (
            Path(weights_text) if weights_text else repo_path / "vanilla_model_weights"
        )
        if not weights_path.is_dir():
            raise StepError(
                "proteinmpnn_multi_model_consensus: weights_path "
                f"'{weights_path}' is not a directory"
            )
        models = parse_models(str(params.get("models", "v_48_002,v_48_020")))
        num_sequences = int(params.get("num_seq_per_target", 4))
        if num_sequences < 1:
            raise StepError(
                "proteinmpnn_multi_model_consensus: num_seq_per_target must be positive"
            )
        sampling_temp = str(params.get("sampling_temp", "0.1")).strip() or "0.1"
        seed = int(params.get("seed", 1))
        if seed < 0:
            raise StepError(
                "proteinmpnn_multi_model_consensus: seed must not be negative"
            )
        chains = str(params.get("chains", "")).strip().replace(" ", "")
        device = str(params.get("device", "cpu"))
        if device not in {"cpu", "cuda"}:
            raise StepError(
                "proteinmpnn_multi_model_consensus: device must be 'cpu' or 'cuda'"
            )
        timeout = float(params.get("timeout", 1800.0))
        if timeout <= 0:
            raise StepError(
                "proteinmpnn_multi_model_consensus: timeout must be positive"
            )
        position_dim = str(params.get("position_dim", "position"))
        amino_acid_dim = str(params.get("amino_acid_dim", "amino_acid"))
        if position_dim == amino_acid_dim:
            raise StepError(
                "proteinmpnn_multi_model_consensus: position_dim and amino_acid_dim "
                "must differ"
            )
        output = str(params.get("output", "consensus"))

        per_model: dict[str, list[str]] = {}
        started = time.monotonic()
        for model_name in models:
            out_dir = Path(tempfile.mkdtemp(prefix="operon-consensus-"))
            try:
                command = [
                    _python(params),
                    runner.as_posix(),
                    "--pdb_path", structure_path.as_posix(),
                    "--out_folder", out_dir.as_posix(),
                    "--num_seq_per_target", str(num_sequences),
                    "--sampling_temp", sampling_temp,
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
                        "proteinmpnn_multi_model_consensus: protein_mpnn_run.py failed "
                        f"for {model_name} with exit code {completed.returncode}: {tail}"
                    )
                fasta = out_dir / "seqs" / f"{structure_path.stem}.fa"
                if not fasta.is_file():
                    raise StepError(
                        "proteinmpnn_multi_model_consensus: the designer produced no "
                        f"FASTA for {model_name} at {fasta}"
                    )
                designs = parse_design_fasta(fasta)
                if not designs:
                    raise StepError(
                        "proteinmpnn_multi_model_consensus: the designer FASTA for "
                        f"{model_name} has no generated designs"
                    )
                per_model[model_name] = [
                    record["sequence"] for record in designs
                ]
            except subprocess.TimeoutExpired as exc:
                raise StepError(
                    "proteinmpnn_multi_model_consensus: the designer timed out after "
                    f"{timeout:.0f}s"
                ) from exc
            finally:
                shutil.rmtree(out_dir, ignore_errors=True)

        sequences = [sequence for group in per_model.values() for sequence in group]
        length = len(sequences[0])
        frequencies = position_frequencies(sequences, length)
        consensus = consensus_sequence(frequencies)
        agreement = frequencies.max(axis=1).astype(np.float32)
        ctx[output] = Form(
            data=frequencies,
            dims=[position_dim, amino_acid_dim],
            labels={
                position_dim: {
                    str(position + 1): position for position in range(length)
                },
                amino_acid_dim: {
                    residue: position for position, residue in enumerate(AA_ORDER)
                },
            },
            info={
                "missing_code": np.nan,
                "consensus": consensus,
                "agreement": agreement.tolist(),
                "designs_per_model": {
                    name: len(group) for name, group in per_model.items()
                },
                "sequences_per_model": per_model,
                "n_designs": len(sequences),
                "n_models": len(models),
                "models": models,
                "aa_order": AA_ORDER,
            },
        )
        elapsed = time.monotonic() - started
        self._export_data = {
            "models": models,
            "consensus": consensus,
            "n_designs": len(sequences),
            "mean_agreement": round(float(agreement.mean()), 4),
            "sequences_per_model": per_model,
            "elapsed_seconds": round(elapsed, 3),
        }
        print(
            f"[proteinmpnn_multi_model_consensus] {len(sequences)} designs from "
            f"{len(models)} models ({length} positions, {elapsed:.1f}s)"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _python(params: dict) -> str:
    executable = str(params.get("python_executable", "")).strip()
    if executable:
        return executable
    return sys.executable
