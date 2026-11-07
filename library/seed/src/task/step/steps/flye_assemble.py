"""De novo long-read assembly through the official Flye binary."""

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
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps._native_results import output_directory, remember_native, result_file

_MODES = (
    "nano-raw",
    "nano-corr",
    "nano-hq",
    "pacbio-raw",
    "pacbio-corr",
    "pacbio-hifi",
)
_COLUMNS = ("length", "coverage", "is_circular")


def write_fasta(sequences: list[str], path: Path) -> None:
    """Write reads as a plain FASTA file (Flye accepts uncompressed FASTA)."""

    lines: list[str] = []
    for index, sequence in enumerate(sequences):
        lines.append(f">read{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_fasta(text: str) -> list[tuple[str, str]]:
    """Parse a FASTA payload into ``(name, sequence)`` pairs."""

    records: list[tuple[str, str]] = []
    name = ""
    chunks: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if name:
                records.append((name, "".join(chunks).upper()))
            name = line[1:].split()[0] if line[1:].split() else ""
            chunks = []
        else:
            chunks.append(line)
    if name:
        records.append((name, "".join(chunks).upper()))
    return records


def parse_assembly_info(text: str) -> list[dict]:
    """Parse Flye's ``assembly_info.txt`` table."""

    records: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 3:
            raise StepError(
                "flye_assemble: assembly_info.txt carries a malformed row: "
                f"{line[:120]}"
            )
        try:
            length = int(float(fields[1]))
            coverage = float(fields[2])
        except ValueError as error:
            raise StepError(
                "flye_assemble: assembly_info.txt carries a non-numeric length or "
                f"coverage: {line[:120]}"
            ) from error
        length_code = str(fields[3]).strip().lower() if len(fields) > 3 else "n"
        records.append(
            {
                "name": fields[0].strip(),
                "length": length,
                "coverage": coverage,
                "is_circular": 1.0 if length_code in {"y", "yes", "circular"} else 0.0,
            }
        )
    return records


def n50(lengths: list[int]) -> tuple[int, int]:
    """Return ``(N50, L50)`` for a list of contig lengths."""

    ordered = sorted((int(value) for value in lengths), reverse=True)
    total = sum(ordered)
    if not ordered or total <= 0:
        return 0, 0
    running = 0
    for index, length in enumerate(ordered, start=1):
        running += length
        if running >= total / 2:
            return length, index
    return ordered[-1], len(ordered)


def tool_environment(binary: str) -> dict:
    """Prepend the tool directory to PATH so Flye finds minimap2 and friends."""

    env = dict(os.environ)
    folder = str(Path(binary).expanduser().absolute().parent)
    env["PATH"] = folder + os.pathsep + env.get("PATH", "")
    return env


def run_flye(
    binary: str,
    sequences: list[str],
    *,
    mode: str = "nano-raw",
    genome_size: str = "48k",
    threads: int = 4,
    min_overlap: int = 1000,
    timeout: float = 1800.0,
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Assemble reads with Flye and return contig records plus sequences."""

    if mode not in _MODES:
        raise StepError(f"flye_assemble: mode must be one of {', '.join(_MODES)}")
    with tempfile.TemporaryDirectory(prefix="flye_") as tmp:
        folder = Path(tmp)
        reads = folder / "reads.fasta"
        write_fasta(sequences, reads)
        out_dir = folder / "flye_out"
        launcher = (
            [sys.executable, binary]
            if str(binary).lower().endswith(".py")
            else [binary]
        )
        command = [
            *launcher,
            f"--{mode}",
            str(reads),
            "--out-dir",
            str(out_dir),
            "--threads",
            str(max(1, int(threads))),
            "--genome-size",
            str(genome_size),
            "--min-overlap",
            str(max(100, int(min_overlap))),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=tool_environment(binary),
            )
        except FileNotFoundError as error:
            raise StepError(
                f"flye_assemble: '{binary}' was not found on PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise StepError(
                f"flye_assemble: the assembler timed out after {timeout:.0f} s"
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError(
                "flye_assemble: the assembler failed with exit code "
                f"{completed.returncode}: {' | '.join(tail[-3:])}"
            )
        assembly = out_dir / "assembly.fasta"
        if not assembly.is_file():
            raise StepError("flye_assemble: the assembler produced no assembly.fasta")
        info = out_dir / "assembly_info.txt"
        records = (
            parse_assembly_info(info.read_text(encoding="utf-8", errors="replace"))
            if info.is_file()
            else []
        )
        contigs = parse_fasta(assembly.read_text(encoding="utf-8", errors="replace"))
    return records, contigs


class FlyeAssembleStep(Step):
    provider = "operon-core"
    parameters_file = "flye_assemble.FlyeAssembleStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "flye_assemble",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Flye de novo assembly",
        "description": (
            "Assemble long reads de novo with the official Flye binary and report "
            "contig lengths, coverage and circularity."
        ),
        "category": "Genome",
        "icon": "Dna",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"}
                    },
                }
            ],
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
            "estimate": "estimate_memory",
            "external_tools": ["flye"],
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        sequences = decode_sequences(
            inputs[0],
            str(params.get("sequence_dim", "sequence")),
            str(params.get("position_dim", "position")),
        )
        if not sequences:
            raise StepError("flye_assemble: the input carries no read sequence")
        mode = str(params.get("mode", "nano-raw"))
        if mode not in _MODES:
            raise StepError(f"flye_assemble: mode must be one of {', '.join(_MODES)}")
        binary = str(params.get("flye_path") or "flye")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError(
                "flye_assemble: the Flye executable was not found; set flye_path "
                "to its location"
            )
        directory = output_directory(ctx, "flye")
        native_fasta = directory / "assembly.fasta"
        records, contigs = run_flye(
            resolved,
            sequences,
            mode=str(params.get("mode", "nano-raw")),
            genome_size=str(params.get("genome_size", "48k")),
            threads=int(params.get("threads", 4)),
            min_overlap=int(params.get("min_overlap", 1000)),
            timeout=float(params.get("timeout_seconds", 1800)),
        )
        write_fasta([sequence for _, sequence in contigs], native_fasta)
        by_name = {record["name"]: record for record in records}
        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        names: list[str] = []
        for name, _sequence in contigs:
            record = by_name.get(name)
            if record is None:
                record = {"length": len(_sequence), "coverage": 0.0, "is_circular": 0.0}
            labels[name] = len(rows)
            names.append(name)
            rows.append([record["length"], record["coverage"], record["is_circular"]])
        lengths = [int(row[0]) for row in rows]
        n50_value, l50_value = n50(lengths)
        data = (
            np.asarray(rows, dtype=np.float32)
            if rows
            else np.zeros((0, len(_COLUMNS)), dtype=np.float32)
        )
        ctx[out_name] = Form(
            data=data,
            dims=["contig", "statistic"],
            labels={
                "contig": labels,
                "statistic": {name: index for index, name in enumerate(_COLUMNS)},
            },
            info={
                "missing_code": np.nan,
                "source": "flye",
                "mode": str(params.get("mode", "nano-raw")),
                "genome_size": str(params.get("genome_size", "48k")),
                "n_contigs": len(rows),
                "total_length": int(sum(lengths)),
                "n50": int(n50_value),
                "l50": int(l50_value),
                "largest": int(max(lengths)) if lengths else 0,
                "mean_coverage": float(np.mean([row[1] for row in rows])) if rows else 0.0,
                "contigs": names,
            },
        )
        result_files = [result_file("assembly", native_fasta, "fasta", "Flye assembly")]
        remember_native(ctx, str(out_name), result_files)
        self._export_data = {
            "output": out_name,
            "result_files": result_files,
            "n_contigs": len(rows),
            "total_length": int(sum(lengths)),
            "n50": int(n50_value),
            "l50": int(l50_value),
        }

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
