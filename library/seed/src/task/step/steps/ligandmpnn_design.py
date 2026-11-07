"""Sequence design with the official LigandMPNN runner."""

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

_AA_ALPHABET = "ACDEFGHIKLMNPQRSTVWYX"
_MODEL_TYPES = ("ligand_mpnn", "protein_mpnn", "soluble_mpnn")
_CHECKPOINT_FLAG = {
    "ligand_mpnn": "--checkpoint_ligand_mpnn",
    "protein_mpnn": "--checkpoint_protein_mpnn",
    "soluble_mpnn": "--checkpoint_soluble_mpnn",
}
_STATISTICS = ("overall_confidence", "ligand_confidence", "seq_recovery")

_HEADER_FIELD = re.compile(r"([A-Za-z_]+)=([^,]+)")


def _repo_path(value: str) -> Path:
    text = value or os.environ.get("OPERON_LIGANDMPNN_PATH", "")
    if not text:
        raise StepError(
            "ligandmpnn_design: ligandmpnn_path is required; point it at a LigandMPNN checkout "
            "or set OPERON_LIGANDMPNN_PATH"
        )
    return Path(text).expanduser()


def _python(value: str) -> str:
    text = value or ""
    return text or shutil.which("python3") or "python"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - torch is optional
        return False


def parse_design_fasta(path: Path) -> list[dict]:
    """Read the generated records from a LigandMPNN FASTA file."""
    if not path.is_file():
        raise StepError(f"ligandmpnn_design: the runner produced no FASTA file at {path}")
    records: list[dict] = []
    header: str | None = None
    sequence_lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith(">"):
            if header is not None:
                _consume(header, sequence_lines, records)
            header = line[1:]
            sequence_lines = []
        elif header is not None and line:
            sequence_lines.append(line)
    if header is not None:
        _consume(header, sequence_lines, records)
    if not records:
        raise StepError(
            "ligandmpnn_design: the FASTA file has no generated sequences; "
            "check that --number_of_batches and --batch_size are at least 1"
        )
    records.sort(key=lambda record: record["sample"])
    return records


def _consume(header: str, sequence_lines: list[str], records: list[dict]) -> None:
    fields = {name: value.strip() for name, value in _HEADER_FIELD.findall(header)}
    if "id" not in fields:
        return
    try:
        sample = int(fields["id"])
    except ValueError as error:
        raise StepError(f"ligandmpnn_design: cannot parse design id from header '{header}'") from error
    record = {
        "sample": sample,
        "overall_confidence": float(fields.get("overall_confidence", "nan")),
        "ligand_confidence": float(fields.get("ligand_confidence", "nan")),
        "seq_recovery": float(fields.get("seq_rec", "nan")),
        "sequence": "".join(sequence_lines).replace("\n", ""),
    }
    records.append(record)


def _parse_residues(value: str, label: str) -> list[str]:
    tokens = [token for token in value.replace(",", " ").split() if token]
    for token in tokens:
        match = re.fullmatch(r"([A-Za-z])(-?\d+)[A-Za-z]?", token)
        if match is None:
            raise StepError(f"ligandmpnn_design: {label} token '{token}' is not of the form A12")
    return tokens


def _parse_amino_acids(value: str) -> str:
    text = value.replace(",", "").replace(" ", "").upper()
    for char in text:
        if char not in _AA_ALPHABET:
            raise StepError(f"ligandmpnn_design: '{char}' is not an amino acid letter")
    return text


def _parse_bias(value: str) -> str:
    for token in [item for item in value.replace(" ", "").split(",") if item]:
        letter, separator, weight = token.partition(":")
        if not separator:
            letter, separator, weight = token.partition("=")
        if letter.upper() not in _AA_ALPHABET or not separator:
            raise StepError(f"ligandmpnn_design: bias token '{token}' is not of the form A:-1.0")
        try:
            float(weight)
        except ValueError as error:
            raise StepError(f"ligandmpnn_design: bias weight '{weight}' is not a number") from error
    return value


class LigandMpnnDesignStep(Step):
    provider = "operon-core"
    parameters_file = "ligandmpnn_design.LigandMpnnDesignStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "ligandmpnn_design",
        "kind": "operator",
        "version": "1.0.0",
        "title": "LigandMPNN Design",
        "description": (
            "Design protein sequences on a fixed backbone with the official LigandMPNN "
            "runner, including ligand- and side-chain-aware context, per-residue bias, "
            "omitted residues and redesign ranges."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
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
        structure = Path(str(params.get("structure_path", ""))).expanduser()
        if not str(params.get("structure_path", "")).strip():
            raise StepError("ligandmpnn_design: structure_path is required")
        if not structure.is_file():
            raise StepError(f"ligandmpnn_design: structure_path '{structure}' is not a file")
        repo = _repo_path(str(params.get("ligandmpnn_path", "")))
        runner = repo / "run.py"
        if not runner.is_file():
            raise StepError(f"ligandmpnn_design: '{runner}' does not look like a LigandMPNN checkout")
        weights = Path(str(params.get("weights_path", ""))).expanduser()
        if not str(params.get("weights_path", "")).strip():
            raise StepError("ligandmpnn_design: weights_path is required")
        if not weights.is_file():
            raise StepError(f"ligandmpnn_design: weights_path '{weights}' is not a file")

        model_type = str(params.get("model_type", "ligand_mpnn"))
        if model_type not in _MODEL_TYPES:
            raise StepError(f"ligandmpnn_design: model_type must be one of {list(_MODEL_TYPES)}")
        device = str(params.get("device", "cpu"))
        if device not in ("cpu", "cuda"):
            raise StepError("ligandmpnn_design: device must be 'cpu' or 'cuda'")
        if device == "cuda" and not _cuda_available():
            raise StepError("ligandmpnn_design: device 'cuda' was requested but CUDA is not available")
        temperature = float(params.get("temperature", 0.1))
        if not 0.0 < temperature <= 5.0:
            raise StepError("ligandmpnn_design: temperature must be in (0, 5]")
        number_of_batches = int(params.get("number_of_batches", 1))
        if number_of_batches < 1:
            raise StepError("ligandmpnn_design: number_of_batches must be at least 1")
        batch_size = int(params.get("batch_size", 1))
        if not 1 <= batch_size <= 64:
            raise StepError("ligandmpnn_design: batch_size must be between 1 and 64")
        seed = int(params.get("seed", 1))
        if seed < 0 or seed > 2**31 - 1:
            raise StepError("ligandmpnn_design: seed must be between 0 and 2147483647")
        timeout = int(params.get("timeout_seconds", 3600))
        if timeout < 1:
            raise StepError("ligandmpnn_design: timeout_seconds must be positive")
        cutoff = float(params.get("ligand_mpnn_cutoff_for_score", 8.0))
        if not 0.0 < cutoff <= 20.0:
            raise StepError("ligandmpnn_design: ligand_mpnn_cutoff_for_score must be in (0, 20]")

        chains = str(params.get("chains_to_design", "")).replace(" ", "")
        fixed = _parse_residues(str(params.get("fixed_positions", "")), "fixed_positions")
        redesigned = _parse_residues(str(params.get("redesigned_residues", "")), "redesigned_residues")
        overlap = set(fixed) & set(redesigned)
        if overlap:
            sample = sorted(overlap)[0]
            raise StepError(f"ligandmpnn_design: '{sample}' cannot be fixed and redesigned at once")
        omit = _parse_amino_acids(str(params.get("omit_AA", "")))
        bias = _parse_bias(str(params.get("bias_AA", "")))

        python = _python(str(params.get("python_executable", "")))
        output = str(params.get("output", "output"))
        out_dir = Path(tempfile.mkdtemp(prefix="operon-ligandmpnn-"))
        environment = dict(os.environ)
        if device == "cpu":
            environment["CUDA_VISIBLE_DEVICES"] = ""
        command = [
            python,
            runner.name,
            "--pdb_path",
            structure.as_posix(),
            "--out_folder",
            out_dir.as_posix(),
            "--model_type",
            model_type,
            _CHECKPOINT_FLAG[model_type],
            weights.as_posix(),
            "--temperature",
            str(temperature),
            "--seed",
            str(seed),
            "--number_of_batches",
            str(number_of_batches),
            "--batch_size",
            str(batch_size),
            "--ligand_mpnn_use_atom_context",
            "1" if bool(params.get("ligand_mpnn_use_atom_context", True)) else "0",
            "--ligand_mpnn_use_side_chain_context",
            "1" if bool(params.get("ligand_mpnn_use_side_chain_context", False)) else "0",
            "--ligand_mpnn_cutoff_for_score",
            str(cutoff),
        ]
        if chains:
            command += ["--chains_to_design", chains]
        if fixed:
            command += ["--fixed_residues", " ".join(fixed)]
        if redesigned:
            command += ["--redesigned_residues", " ".join(redesigned)]
        if omit:
            command += ["--omit_AA", omit]
        if bias:
            command += ["--bias_AA", bias]

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
            raise StepError(f"ligandmpnn_design: the runner timed out after {timeout} seconds") from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-6:]
            detail = " | ".join(tail) if tail else "no runner output"
            raise StepError(f"ligandmpnn_design: the runner failed with exit code {completed.returncode}: {detail}")

        stem = structure.stem
        try:
            records = parse_design_fasta(out_dir / "seqs" / f"{stem}.fa")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
        if any(not np.isfinite([record[name] for name in _STATISTICS]).all() for record in records):
            raise StepError(
                "ligandmpnn_design: the runner reported non-finite confidences; "
                "check that the structure carries protein backbone atoms and, for ligand_mpnn, ligand atoms"
            )

        data = np.asarray([[record[name] for name in _STATISTICS] for record in records], dtype=np.float32)
        labels = [f"design{record['sample']}" for record in records]
        out = Form(
            data=data,
            dims=["design", "statistic"],
            labels={
                "design": {label: index for index, label in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "sequences": [record["sequence"] for record in records],
                "n_designs": len(records),
                "structure_path": str(structure),
                "model_type": model_type,
                "chains_to_design": chains,
                "fixed_positions": fixed,
                "redesigned_residues": redesigned,
                "omit_AA": omit,
                "bias_AA": bias,
                "temperature": temperature,
                "seed": seed,
                "number_of_batches": number_of_batches,
                "batch_size": batch_size,
                "device": device,
                "metric": "confidence=exp(-mean_nll), higher is better",
            },
        )
        out.validate()
        ctx[output] = out
        self._export_data = {
            "designs": len(records),
            "sequences": out.info["sequences"],
            "mean_overall_confidence": float(np.mean(data[:, 0])),
            "model_type": model_type,
            "structure_path": str(structure),
        }
        print(
            f"ligandmpnn_design: {len(records)} designs, mean overall confidence "
            f"{float(np.mean(data[:, 0])):.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
