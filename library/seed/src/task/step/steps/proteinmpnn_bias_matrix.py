"""Per-residue amino-acid bias design with the official ProteinMPNN runner."""

from __future__ import annotations

import json
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

from .proteinmpnn_design import (
    MODELS,
    parse_design_fasta,
    parse_positions,
    pdb_chains,
)


BIAS_ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"


def _resolve_weights(repo: Path, text: str) -> Path:
    raw = str(text or "").strip()
    weights = Path(raw).expanduser() if raw else repo / "vanilla_model_weights"
    if not weights.is_dir():
        raise StepError(
            "proteinmpnn_bias_matrix: weights directory "
            f"{weights} does not exist; set weights_path to the directory holding v_48_*.pt"
        )
    return weights


def bias_matrix(
    chains: dict[str, list[int]],
    positions: dict[str, list[int]],
    *,
    favor: str,
    avoid: str,
    strength: float,
) -> dict[str, list[list[float]]]:
    """Return ``{chain: [[21 floats] per residue]}`` in the official order."""

    for residue in favor + avoid:
        if residue not in BIAS_ALPHABET:
            raise StepError(
                f"proteinmpnn_bias_matrix: residue {residue!r} is not a standard amino acid"
            )
    matrix: dict[str, list[list[float]]] = {}
    for chain, residues in chains.items():
        block = [[0.0] * 21 for _ in residues]
        targets = set(positions.get(chain, []))
        for index, number in enumerate(residues):
            if number not in targets:
                continue
            for residue in favor:
                block[index][BIAS_ALPHABET.index(residue)] = strength
            for residue in avoid:
                block[index][BIAS_ALPHABET.index(residue)] = -strength
        matrix[chain] = block
    return matrix


def bias_payload(
    chains: dict[str, list[int]],
    positions: dict[str, list[int]],
    *,
    stem: str,
    favor: str,
    avoid: str,
    strength: float,
) -> dict:
    """Validate the requested positions and return the official payload."""

    if not positions:
        raise StepError("proteinmpnn_bias_matrix: positions must name at least one residue")
    for chain, numbers in positions.items():
        if chain not in chains:
            raise StepError(
                f"proteinmpnn_bias_matrix: chain {chain} is not in the structure"
            )
        present = set(chains[chain])
        unknown = [number for number in numbers if number not in present]
        if unknown:
            raise StepError(
                f"proteinmpnn_bias_matrix: residue {unknown[0]} is not an author "
                f"residue number of chain {chain}"
            )
    if not favor and not avoid:
        raise StepError("proteinmpnn_bias_matrix: favor and avoid are both empty")
    return {stem: bias_matrix(chains, positions, favor=favor, avoid=avoid, strength=strength)}


def run_bias_designer(
    params: dict, structure: Path, chain_text: str, payload: dict, weights: Path, repo: Path
) -> list[dict]:
    """Run the official ProteinMPNN runner with a per-residue bias file."""

    timeout = int(params.get("timeout_seconds", 1800) or 1800)
    device = str(params.get("device", "cpu")).strip() or "cpu"
    executable = str(params.get("python_executable", "")).strip() or sys.executable
    with tempfile.TemporaryDirectory(prefix="operon_bias_") as tmp:
        out_dir = Path(tmp) / "designs"
        out_dir.mkdir()
        bias_path = Path(tmp) / "bias.jsonl"
        bias_path.write_text(json.dumps(payload) + "\n")
        command = [
            executable,
            str(repo / "protein_mpnn_run.py"),
            "--pdb_path",
            structure.as_posix(),
            "--out_folder",
            out_dir.as_posix(),
            "--num_seq_per_target",
            str(int(params.get("num_seq_per_target", 8) or 8)),
            "--sampling_temp",
            str(params.get("sampling_temp", "0.1")),
            "--seed",
            str(int(params.get("seed", 1) or 1)),
            "--suppress_print",
            "1",
            "--model_name",
            str(params.get("model_name", "v_48_020")),
            "--bias_by_res_jsonl",
            bias_path.as_posix(),
            "--path_to_model_weights",
            weights.as_posix(),
        ]
        if chain_text:
            command += ["--pdb_path_chains", chain_text]
        env = dict(os.environ)
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
        env["CUDA_VISIBLE_DEVICES"] = "" if device == "cpu" else "0"
        try:
            completed = subprocess.run(
                command,
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise StepError(
                f"proteinmpnn_bias_matrix: the designer timed out after {timeout} s"
            ) from exc
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
            raise StepError(
                "proteinmpnn_bias_matrix: the designer failed with exit code "
                f"{completed.returncode}: {' | '.join(tail)}"
            )
        fasta = out_dir / "seqs" / f"{structure.stem}.fa"
        if not fasta.is_file():
            raise StepError(f"proteinmpnn_bias_matrix: the designer produced no FASTA at {fasta}")
        return parse_design_fasta(fasta)


class ProteinmpnnBiasMatrixStep(Step):
    """Bias selected positions towards (or away from) amino acids."""

    provider = "operon-core"
    parameters_file = (
        "proteinmpnn_bias_matrix.ProteinmpnnBiasMatrixStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_bias_matrix",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN bias matrix",
        "description": (
            "Build a per-residue amino-acid bias matrix for the official ProteinMPNN "
            "runner and return the designs it produces.  Selected "
            "positions are pushed towards the favor residues and away "
            "from the avoid residues."
        ),
        "category": "Machine Learning",
        "icon": "ShareNetwork",
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
        out_name = str(params.get("output", "designs")) or "designs"
        design_dim = str(params.get("design_dim", "design")) or "design"
        structure = Path(str(params.get("structure_path", "")).strip()).expanduser()
        if not structure.is_file():
            raise StepError(
                f"proteinmpnn_bias_matrix: structure_path {structure} is not a file"
            )
        repo = Path(str(params.get("proteinmpnn_path", "")).strip()).expanduser()
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                f"proteinmpnn_bias_matrix: {repo}/protein_mpnn_run.py was not found; "
                "pass proteinmpnn_path pointing at the official ProteinMPNN checkout"
            )
        weights = _resolve_weights(repo, str(params.get("weights_path", "")))
        model = str(params.get("model_name", "v_48_020")).strip() or "v_48_020"
        if model not in MODELS:
            raise StepError(
                f"proteinmpnn_bias_matrix: model_name must be one of {', '.join(MODELS)}"
            )
        device = str(params.get("device", "cpu")).strip() or "cpu"
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_bias_matrix: device must be 'cpu' or 'cuda'")
        strength = float(params.get("strength", 1.0))
        if strength <= 0:
            raise StepError("proteinmpnn_bias_matrix: strength must be positive")

        chains = pdb_chains(structure)
        if not chains:
            raise StepError(
                "proteinmpnn_bias_matrix: the structure file carries no ATOM residues"
            )
        positions = parse_positions(str(params.get("positions", "")))
        favor = str(params.get("favor", "WYFH")).strip().upper() or "WYFH"
        avoid = str(params.get("avoid", "")).strip().upper()
        chain_text = str(params.get("chains", "")).strip()
        selected = sorted({chain for chain in positions})
        if chain_text:
            selected = sorted(set(chain_text.split()))
        payload = bias_payload(
            chains,
            {chain: positions[chain] for chain in selected if chain in positions},
            stem=structure.stem,
            favor=favor,
            avoid=avoid,
            strength=strength,
        )
        records = run_bias_designer(params, structure, " ".join(selected), payload, weights, repo)
        if not records:
            raise StepError("proteinmpnn_bias_matrix: the designer returned no sequences")

        labels = {
            design_dim: {f"design{index + 1}": index for index in range(len(records))},
            "statistic": {"score": 0, "global_score": 1},
        }
        data = np.zeros((len(records), 2), dtype=np.float32)
        for index, record in enumerate(records):
            data[index] = (record["score"], record["global_score"])
        ctx[out_name] = Form(
            data=data,
            dims=[design_dim, "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "sequences": [record["sequence"] for record in records],
                "bias_positions": {chain: positions[chain] for chain in sorted(positions)},
                "favor": favor,
                "avoid": avoid,
                "strength": strength,
                "model_name": model,
                "n_designs": len(records),
            },
        )
        self._export_data = {
            "n_designs": len(records),
            "sequences": [record["sequence"] for record in records],
            "bias_positions": {chain: positions[chain] for chain in sorted(positions)},
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
