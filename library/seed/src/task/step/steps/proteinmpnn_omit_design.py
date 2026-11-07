"""Constrained amino-acid design with the official ProteinMPNN runner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from .proteinmpnn_design import MODELS, parse_design_fasta, pdb_chains

AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"
_STATISTICS = ("score", "global_score")


def parse_omit(text: str) -> str:
    """Return the canonical space-free omitted amino-acid letters."""

    letters = str(text or "").replace(",", " ").replace(";", " ").split()
    cleaned = []
    for token in letters:
        for char in token.strip().upper():
            if char not in AA_ALPHABET:
                raise StepError(
                    f"proteinmpnn_omit_design: '{char}' is not a standard amino-acid letter"
                )
            if char not in cleaned:
                cleaned.append(char)
    if not cleaned:
        raise StepError("proteinmpnn_omit_design: omit_AAs must list at least one amino acid")
    if len(cleaned) >= len(AA_ALPHABET):
        raise StepError(
            "proteinmpnn_omit_design: at least one amino acid must remain designable"
        )
    return "".join(sorted(cleaned))


def omit_command(
    params: dict,
    structure: Path,
    out_dir: Path,
    chains_text: str,
    omit: str,
    weights: Path,
    repo: Path,
) -> list[str]:
    """Build the official ProteinMPNN command with a global omission set."""

    python = str(params.get("python_executable", "")).strip() or sys.executable
    command = [
        python,
        str(repo / "protein_mpnn_run.py"),
        "--pdb_path",
        structure.as_posix(),
        "--out_folder",
        out_dir.as_posix(),
        "--num_seq_per_target",
        str(int(params.get("num_seq_per_target", 8))),
        "--sampling_temp",
        str(params.get("sampling_temp", "0.1")),
        "--seed",
        str(int(params.get("seed", 1))),
        "--suppress_print",
        "1",
        "--model_name",
        str(params.get("model_name", "v_48_020")),
        "--path_to_model_weights",
        weights.as_posix(),
        "--omit_AAs",
        " ".join(omit),
    ]
    if chains_text:
        command += ["--pdb_path_chains", chains_text]
    return command


def run_omit_designer(
    params: dict,
    structure: Path,
    chains_text: str,
    omit: str,
    weights: Path,
    repo: Path,
) -> list[dict]:
    timeout = int(params.get("timeout_seconds", 1800) or 1800)
    with tempfile.TemporaryDirectory(prefix="operon_omit_") as tmp:
        out_dir = Path(tmp) / "designs"
        out_dir.mkdir()
        command = omit_command(params, structure, out_dir, chains_text, omit, weights, repo)
        env = dict(os.environ)
        env["CUDA_VISIBLE_DEVICES"] = "" if str(params.get("device", "cpu")) == "cpu" else "0"
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
                f"proteinmpnn_omit_design: the designer timed out after {timeout} s"
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
            raise StepError(
                "proteinmpnn_omit_design: the designer failed with exit code "
                f"{completed.returncode}: {' | '.join(tail)}"
            )
        fasta = out_dir / "seqs" / (structure.stem + ".fa")
        if not fasta.is_file():
            raise StepError(
                f"proteinmpnn_omit_design: the designer produced no FASTA at {fasta}"
            )
        return parse_design_fasta(fasta)


def _resolve_weights(repo: Path, text: str) -> Path:
    raw = str(text or "").strip()
    weights = Path(raw).expanduser() if raw else repo / "vanilla_model_weights"
    if not weights.is_dir():
        raise StepError(
            "proteinmpnn_omit_design: weights directory "
            f"{weights} does not exist; set weights_path to the directory holding v_48_*.pt"
        )
    return weights


class ProteinmpnnOmitDesignStep(Step):
    """Design sequences while forbidding a set of amino acids."""

    provider = "operon-core"
    parameters_file = "proteinmpnn_omit_design.ProteinmpnnOmitDesignStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "proteinmpnn_omit_design",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ProteinMPNN constrained design",
        "description": (
            "Run the official ProteinMPNN sampler with a global amino-acid omission "
            "set (for example cysteine-free design) and report the sampled designs."
        ),
        "category": "Machine Learning",
        "icon": "Scissors",
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
                f"proteinmpnn_omit_design: structure_path {structure} is not a file"
            )
        if structure.suffix.lower() not in (".pdb", ".ent"):
            raise StepError("proteinmpnn_omit_design: structure_path must name a .pdb file")
        repo = Path(str(params.get("proteinmpnn_path", "")).strip()).expanduser()
        if not (repo / "protein_mpnn_run.py").is_file():
            raise StepError(
                f"proteinmpnn_omit_design: {repo}/protein_mpnn_run.py was not found; "
                "pass proteinmpnn_path pointing at the official ProteinMPNN checkout"
            )
        weights = _resolve_weights(repo, str(params.get("weights_path", "")))
        model = str(params.get("model_name", "v_48_020")).strip() or "v_48_020"
        if model not in MODELS:
            raise StepError(
                f"proteinmpnn_omit_design: model_name must be one of {', '.join(MODELS)}"
            )
        device = str(params.get("device", "cpu")).strip() or "cpu"
        if device not in ("cpu", "cuda"):
            raise StepError("proteinmpnn_omit_design: device must be 'cpu' or 'cuda'")
        omit = parse_omit(str(params.get("omit_AAs", "C")))
        chains = pdb_chains(structure)
        if not chains:
            raise StepError("proteinmpnn_omit_design: the structure file carries no ATOM residues")
        chains_text = str(params.get("chains", "")).strip()
        selected = sorted(set(chains_text.split())) if chains_text else sorted(chains)
        unknown = [chain for chain in selected if chain not in chains]
        if unknown:
            raise StepError(
                "proteinmpnn_omit_design: chains "
                f"{', '.join(unknown)} are not in the structure file"
            )

        records = run_omit_designer(
            params, structure, " ".join(selected), omit, weights, repo
        )
        if not records:
            raise StepError("proteinmpnn_omit_design: the designer returned no sequences")

        sequences = [record["sequence"] for record in records]
        leaked = [index for index, text in enumerate(sequences) if any(c in text for c in omit)]
        if leaked:
            raise StepError(
                "proteinmpnn_omit_design: the designer returned omitted residues; "
                "check the ProteinMPNN version and the --omit_AAs argument"
            )
        labels = {
            design_dim: {f"design{index + 1}": index for index in range(len(records))},
            "statistic": {name: index for index, name in enumerate(_STATISTICS)},
        }
        data = np.zeros((len(records), len(_STATISTICS)), dtype=np.float32)
        for index, record in enumerate(records):
            data[index] = (record["score"], record["global_score"])
        ctx[out_name] = Form(
            data=data,
            dims=[design_dim, "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "sequences": sequences,
                "omit_AAs": omit,
                "chains": selected,
                "model_name": model,
                "n_designs": len(records),
            },
        )
        self._export_data = {
            "n_designs": len(records),
            "omit_AAs": omit,
            "sequences": sequences,
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
