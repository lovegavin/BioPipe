"""Prokaryotic gene prediction through the official Prodigal binary."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_STATISTICS = ("start", "end", "strand", "length", "partial_code")
_MODES = ("single", "meta")


def write_fasta(sequences: list[str], path: Path) -> None:
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f">contig{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_gff(text: str) -> list[dict]:
    """Parse Prodigal GFF3 rows into CDS gene records."""

    records: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 9 or fields[2] != "CDS":
            continue
        try:
            begin = int(fields[3])
            end = int(fields[4])
        except ValueError as error:
            raise StepError(
                "prodigal_genes: the GFF output carries a non-integer coordinate"
            ) from error
        strand = fields[6]
        if strand not in ("+", "-"):
            raise StepError(
                f"prodigal_genes: unexpected strand '{strand}' in the GFF output"
            )
        attributes = {}
        for piece in fields[8].strip().strip(";").split(";"):
            if "=" in piece:
                key, value = piece.split("=", 1)
                attributes[key.strip()] = value.strip()
        partial = attributes.get("partial", "00")
        records.append(
            {
                "id": attributes.get("ID", f"gene_{len(records) + 1}"),
                "contig": fields[0].strip(),
                "start": begin,
                "end": end,
                "strand": 1 if strand == "+" else -1,
                "partial": partial,
            }
        )
    return records


def partial_code(value: str) -> int:
    """Encode a Prodigal partial flag (``00``, ``01``, ``10``, ``11``)."""

    text = str(value or "00").strip()
    if text not in ("00", "01", "10", "11"):
        raise StepError(
            f"prodigal_genes: unexpected partial flag '{value}' in the GFF output"
        )
    return int(text, 2)


def parse_proteins(text: str) -> list[str]:
    sequences: list[str] = []
    chunks: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if chunks:
                sequences.append("".join(chunks))
                chunks = []
        else:
            chunks.append(line)
    if chunks:
        sequences.append("".join(chunks))
    return sequences


def run_prodigal(
    binary: Path,
    sequences: list[str],
    *,
    mode: str = "single",
    timeout: float = 600.0,
) -> tuple[list[dict], list[str]]:
    """Run Prodigal on one or more contigs and return genes plus proteins."""

    if mode not in _MODES:
        raise StepError(
            f"prodigal_genes: mode must be one of {', '.join(_MODES)}"
        )
    with tempfile.TemporaryDirectory(prefix="prodigal_") as tmp:
        folder = Path(tmp)
        fasta = folder / "contigs.fna"
        write_fasta(sequences, fasta)
        gff_path = folder / "genes.gff"
        protein_path = folder / "proteins.faa"
        launcher = (
            [sys.executable, str(binary)]
            if str(binary).lower().endswith(".py")
            else [str(binary)]
        )
        command = [
            *launcher,
            "-i",
            str(fasta),
            "-o",
            str(gff_path),
            "-a",
            str(protein_path),
            "-f",
            "gff",
            "-p",
            mode,
            "-q",
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise StepError(
                f"prodigal_genes: '{binary}' was not found on PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise StepError(
                f"prodigal_genes: the predictor timed out after {timeout:.0f} s"
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError(
                "prodigal_genes: the predictor failed with exit code "
                f"{completed.returncode}: {' | '.join(tail[-3:])}"
            )
        if not gff_path.is_file():
            raise StepError(
                "prodigal_genes: the predictor produced no GFF output"
            )
        genes = parse_gff(gff_path.read_text(encoding="utf-8", errors="replace"))
        proteins = (
            parse_proteins(protein_path.read_text(encoding="utf-8", errors="replace"))
            if protein_path.is_file()
            else []
        )
    return genes, proteins



def _jsonable(value):
    """Convert numpy values into JSON-serialisable Python objects."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _export_summary(form) -> dict:
    """Build the export payload for one result Form."""
    return {
        "dims": list(form.dims),
        "labels": _jsonable(form.labels),
        "info": _jsonable(
            {key: value for key, value in form.info.items() if key != "missing_code"}
        ),
    }

class ProdigalGenesStep(Step):
    provider = "operon-core"
    parameters_file = "prodigal_genes.ProdigalGenesStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "prodigal_genes",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Prodigal gene prediction",
        "category": "Sequence",
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Predict prokaryotic genes with the official Prodigal binary; "
            "returns gene spans, strand, partial flags and the predicted "
            "protein sequences."
        ),
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
            raise StepError("prodigal_genes: the input carries no sequence")
        binary_text = str(params.get("prodigal_path", "") or "").strip() or os.environ.get(
            "OPERON_PRODIGAL_PATH", ""
        )
        binary = Path(binary_text).expanduser() if binary_text else Path("prodigal")
        genes, proteins = run_prodigal(
            binary,
            sequences,
            mode=str(params.get("mode", "single") or "single"),
            timeout=float(params.get("timeout_seconds", 600.0)),
        )
        if not genes:
            raise StepError(
                "prodigal_genes: the predictor found no coding sequence"
            )
        rows = [
            (
                gene["start"],
                gene["end"],
                gene["strand"],
                gene["end"] - gene["start"] + 1,
                partial_code(gene["partial"]),
            )
            for gene in genes
        ]
        data = np.asarray(rows, dtype=np.float32)
        labels = {f"gene{index + 1}": index for index in range(len(genes))}
        result = Form(
            data=data,
            dims=["gene", "statistic"],
            labels={
                "gene": labels,
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_genes": len(genes),
                "n_partial": sum(1 for gene in genes if gene["partial"] != "00"),
                "mode": str(params.get("mode", "single")),
                "proteins": proteins,
                "genes": genes,
                "n_contigs": len(sequences),
            },
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return self._export_data
