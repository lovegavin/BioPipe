"""AMR and virulence gene detection through the official AMRFinderPlus binary."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._resources_common import check_resource, load_resources, remedy
from src.task.step.steps._sequence_common import decode_sequences


def _tool_env(binary: Path) -> dict:
    """Make helper binaries from the tool's own environment visible."""
    env = dict(os.environ)
    env["PATH"] = str(Path(binary).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env

_STATISTICS = ("start", "stop", "target_length", "reference_length",
               "coverage", "identity", "alignment_length")
_COLUMNS = {
    "contig": ("contig id", "contig"),
    "start": ("start",),
    "stop": ("stop",),
    "strand": ("strand",),
    "gene": ("element symbol", "gene symbol"),
    "name": ("element name", "gene name"),
    "scope": ("scope",),
    "type": ("type",),
    "subtype": ("subtype",),
    "klass": ("class",),
    "subclass": ("subclass",),
    "method": ("method",),
    "target_length": ("target length",),
    "reference_length": ("reference sequence length",),
    "query": ("protein id", "protein identifier"),
    "coverage": ("% coverage of reference sequence", "% coverage of reference", "coverage"),
    "identity": ("% identity to reference sequence", "% identity to reference", "identity"),
    "alignment_length": ("alignment length",),
    "accession": ("closest reference accession", "accession of closest sequence", "closest accession"),
    "closest": ("closest reference name", "name of closest sequence", "closest sequence"),
}


def write_fasta(sequences: list[str], path: Path) -> None:
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f">query{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _normalise(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


def _number(value: str) -> float:
    text = str(value).strip()
    if not text or text in {"NA", "None", "-"}:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def parse_report(text: str) -> list[dict]:
    """Parse the AMRFinderPlus TSV report into one record per hit."""

    reader = csv.reader(text.splitlines(), delimiter="\t")
    try:
        header = next(reader)
    except StopIteration:
        return []
    lookup: dict[str, int] = {}
    for index, column in enumerate(header):
        lookup.setdefault(_normalise(column), index)
    positions: dict[str, int] = {}
    for key, names in _COLUMNS.items():
        for name in names:
            if name in lookup:
                positions[key] = lookup[name]
                break
    if "gene" not in positions or "type" not in positions:
        raise StepError(f"amrfinder_plus: unexpected report header: {header}")
    hits: list[dict] = []
    for fields in reader:
        if not fields or not any(field.strip() for field in fields):
            continue
        def value(key: str) -> str:
            index = positions.get(key)
            return fields[index].strip() if index is not None and index < len(fields) else ""
        hits.append({
            "query": value("query"),
            "contig": value("contig"),
            "start": _number(value("start")),
            "stop": _number(value("stop")),
            "strand": value("strand"),
            "gene": value("gene"),
            "name": value("name"),
            "scope": value("scope"),
            "type": value("type"),
            "subtype": value("subtype"),
            "class": value("klass"),
            "subclass": value("subclass"),
            "method": value("method"),
            "target_length": _number(value("target_length")),
            "reference_length": _number(value("reference_length")),
            "coverage": _number(value("coverage")),
            "identity": _number(value("identity")),
            "alignment_length": _number(value("alignment_length")),
            "accession": value("accession"),
            "closest": value("closest"),
        })
    return hits


def run_amrfinder(binary: Path, database: Path, fasta: Path, *, mode: str,
                  organism: str = "", threads: int = 1, timeout: float = 1800.0) -> list[dict]:
    if not database.is_dir():
        raise StepError(f"amrfinder_plus: database directory '{database}' does not exist")
    with tempfile.TemporaryDirectory(prefix="amrfinder_") as tmp:
        report = Path(tmp) / "report.tsv"
        launcher = [sys.executable, str(binary)] if str(binary).lower().endswith(".py") else [str(binary)]
        command = [*launcher, "-d", str(database), "-o", str(report),
                   "--threads", str(max(1, int(threads))), "--quiet"]
        command.extend(["-p" if mode == "protein" else "-n", str(fasta)])
        if organism:
            command.extend(["--organism", organism])
        try:
            completed = subprocess.run(command, check=False, capture_output=True,
                                       text=True, timeout=timeout, env=_tool_env(binary))
        except FileNotFoundError as error:
            raise StepError(f"amrfinder_plus: '{binary}' was not found on PATH") from error
        except subprocess.TimeoutExpired as error:
            raise StepError(f"amrfinder_plus: AMRFinderPlus timed out after {timeout:.0f} s") from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError("amrfinder_plus: AMRFinderPlus failed with exit code "
                            f"{completed.returncode}: {' | '.join(tail[-3:])}")
        if not report.is_file():
            raise StepError("amrfinder_plus: AMRFinderPlus produced no report")
        return parse_report(report.read_text(encoding="utf-8", errors="replace"))


def _jsonable(value):
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
    return {
        "dims": list(form.dims),
        "labels": _jsonable(form.labels),
        "info": _jsonable({key: value for key, value in form.info.items() if key != "missing_code"}),
    }


class AmrfinderPlusStep(Step):
    provider = "operon-core"
    parameters_file = "amrfinder_plus.AmrfinderPlusStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "amrfinder_plus",
        "version": "1.0.0",
        "kind": "operator",
        "title": "AMRFinderPlus resistance genes",
        "category": "Genome",
        "icon": "Shield",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}],
                "labels": [],
                "parallel": [],
                "ndim": 2,
                "info": {"representation": {"type": "string", "const": "sequence_codes"}},
            }],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True,
                           "axis_info_open": True,
                           "info": {"missing_code": {"type": ["number", "null"]}}},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory",
                      "external_tools": ["amrfinder"]},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Detect antimicrobial resistance and virulence genes with the official "
            "AMRFinderPlus binary; returns gene family, class, coordinates, identity and coverage."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        mode = str(params.get("mode", "protein") or "protein")
        if mode not in {"protein", "nucleotide"}:
            raise StepError("amrfinder_plus: mode must be 'protein' or 'nucleotide'")
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")),
                                     str(params.get("position_dim", "position")))
        if not sequences:
            raise StepError("amrfinder_plus: the input carries no sequence")
        database_text = str(params.get("database_dir", "") or "").strip()
        if database_text:
            database = Path(database_text).expanduser()
            if not database.is_dir():
                raise StepError(f"amrfinder_plus: database_dir '{database}' is not a directory")
        else:
            resource = load_resources()["amrfinder"]
            check = check_resource(resource)
            if check["status"] != "ok":
                raise StepError(f"amrfinder_plus: {remedy(check)}")
            database = Path(check["root"])
        binary = Path(str(params.get("amrfinder_path", "") or "amrfinder")).expanduser()
        with tempfile.TemporaryDirectory(prefix="amrfinder_input_") as tmp:
            fasta = Path(tmp) / ("proteins.faa" if mode == "protein" else "contigs.fna")
            write_fasta(sequences, fasta)
            hits = run_amrfinder(binary, database, fasta, mode=mode,
                                 organism=str(params.get("organism", "") or ""),
                                 threads=int(params.get("threads", 1)),
                                 timeout=float(params.get("timeout_seconds", 1800.0)))
        rows = [(hit["start"], hit["stop"], hit["target_length"], hit["reference_length"],
                 hit["coverage"], hit["identity"], hit["alignment_length"]) for hit in hits]
        data = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        labels = {f"{hit['gene'] or 'hit'}:{hit['contig']}:{int(hit['start']) if np.isfinite(hit['start']) else 0}": index
                  for index, hit in enumerate(hits)}
        result = Form(
            data=data,
            dims=["hit", "statistic"],
            labels={"hit": labels,
                    "statistic": {name: index for index, name in enumerate(_STATISTICS)}},
            info={"missing_code": np.nan, "hits": hits, "n_hits": len(hits), "mode": mode,
                  "genes": sorted({hit["gene"] for hit in hits if hit["gene"]}),
                  "classes": sorted({hit["class"] for hit in hits if hit["class"]}),
                  "database": str(database)},
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return getattr(self, "_export_data", {})
