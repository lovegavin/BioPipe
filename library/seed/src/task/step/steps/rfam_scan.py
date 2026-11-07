"""Rfam covariance-model scan through the official cmscan binary."""

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
from src.task.step.steps._resources_common import check_resource, load_resources, remedy
from src.task.step.steps._sequence_common import decode_sequences


def _tool_env(binary: Path) -> dict:
    """Make helper binaries from the tool's own environment visible."""
    env = dict(os.environ)
    env["PATH"] = str(Path(binary).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env

_STATISTICS = ("start", "end", "length", "strand", "score", "evalue", "model_from", "model_to")


def write_fasta(sequences: list[str], path: Path) -> None:
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f">query{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_tblout(text: str) -> list[dict]:
    """Parse a cmscan ``--tblout`` table into per-hit records."""

    hits: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 18:
            continue
        # The default cmscan format omits the clan column; --fmt 2 keeps it.
        if fields[4] in {"cm", "hmm"}:
            base = 4
        elif len(fields) > 5 and fields[5] in {"cm", "hmm"}:
            base = 5
        else:
            continue
        try:
            record = {
                "family": fields[0],
                "accession": fields[1],
                "query": fields[2],
                "model_from": int(fields[base + 1]),
                "model_to": int(fields[base + 2]),
                "start": int(fields[base + 3]),
                "end": int(fields[base + 4]),
                "strand": 1 if fields[base + 5] == "+" else -1,
                "truncated": fields[base + 6] != "no",
                "gc": float(fields[base + 8]),
                "bias": float(fields[base + 9]),
                "score": float(fields[base + 10]),
                "evalue": float(fields[base + 11]),
                "description": " ".join(fields[base + 13:]),
            }
        except (ValueError, IndexError) as error:
            raise StepError(f"rfam_scan: cannot parse a cmscan row: {line!r}") from error
        hits.append(record)
    return hits


def run_cmscan(binary: Path, cm: Path, sequences: list[str], *, evalue: float = 1e-5,
               cpu: int = 1, timeout: float = 1800.0) -> list[dict]:
    if not cm.is_file():
        raise StepError(f"rfam_scan: Rfam covariance model '{cm}' is not a file")
    with tempfile.TemporaryDirectory(prefix="rfam_scan_") as tmp:
        folder = Path(tmp)
        fasta = folder / "queries.fa"
        write_fasta(sequences, fasta)
        table = folder / "hits.tbl"
        launcher = [sys.executable, str(binary)] if str(binary).lower().endswith(".py") else [str(binary)]
        command = [
            *launcher,
            "--tblout", str(table),
            "--noali",
            "--rfam",
            "-E", str(float(evalue)),
            "--cpu", str(max(1, int(cpu))),
            str(cm), str(fasta),
        ]
        try:
            completed = subprocess.run(command, check=False, capture_output=True,
                                       text=True, timeout=timeout, env=_tool_env(binary))
        except FileNotFoundError as error:
            raise StepError(f"rfam_scan: '{binary}' was not found on PATH") from error
        except subprocess.TimeoutExpired as error:
            raise StepError(f"rfam_scan: cmscan timed out after {timeout:.0f} s") from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError("rfam_scan: cmscan failed with exit code "
                            f"{completed.returncode}: {' | '.join(tail[-3:])}")
        if not table.is_file():
            raise StepError("rfam_scan: cmscan produced no tblout file")
        return parse_tblout(table.read_text(encoding="utf-8", errors="replace"))


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


class RfamScanStep(Step):
    provider = "operon-core"
    parameters_file = "rfam_scan.RfamScanStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "rfam_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Rfam ncRNA family scan",
        "category": "Genome",
        "icon": "Database",
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
                      "external_tools": ["cmscan"]},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Scan nucleotide sequences against the Rfam covariance models with "
            "Infernal cmscan; returns family, coordinates, strand, score and E-value."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")),
                                     str(params.get("position_dim", "position")))
        if not sequences:
            raise StepError("rfam_scan: the input carries no sequence")
        cm_text = str(params.get("rfam_cm", "") or "").strip()
        if cm_text:
            cm = Path(cm_text).expanduser()
            if not cm.is_file():
                raise StepError(f"rfam_scan: rfam_cm '{cm}' is not a file")
        else:
            resource = load_resources()["rfam"]
            check = check_resource(resource, root=str(params.get("database_dir", "") or "") or None)
            if check["status"] != "ok":
                raise StepError(f"rfam_scan: {remedy(check)}")
            cm = Path(check["root"]) / "Rfam.cm"
        binary = Path(str(params.get("cmscan_path", "") or "cmscan")).expanduser()
        hits = run_cmscan(binary, cm, sequences,
                          evalue=float(params.get("evalue", 1e-5)),
                          cpu=int(params.get("cpu", 1)),
                          timeout=float(params.get("timeout_seconds", 1800.0)))
        rows = [(hit["start"], hit["end"], hit["end"] - hit["start"] + 1, hit["strand"],
                 hit["score"], hit["evalue"], hit["model_from"], hit["model_to"]) for hit in hits]
        data = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        labels = {f"{hit['query']}:{hit['family']}:{hit['start']}": index
                  for index, hit in enumerate(hits)}
        result = Form(
            data=data,
            dims=["hit", "statistic"],
            labels={"hit": labels,
                    "statistic": {name: index for index, name in enumerate(_STATISTICS)}},
            info={"missing_code": np.nan, "hits": hits, "n_hits": len(hits),
                  "families": sorted({hit["accession"] for hit in hits}),
                  "cm": str(cm)},
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return getattr(self, "_export_data", {})
