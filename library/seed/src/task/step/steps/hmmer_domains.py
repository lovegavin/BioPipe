"""Pfam/HMMER domain annotation through the official hmmscan binary."""

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

_STATISTICS = (
    "evalue",
    "score",
    "hmm_from",
    "hmm_to",
    "ali_from",
    "ali_to",
    "env_from",
    "env_to",
)


def write_fasta(sequences: list[str], path: Path) -> None:
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f">query{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_domtbl(text: str) -> list[dict]:
    """Parse an hmmscan ``--domtblout`` table into per-domain records."""

    records: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 22:
            continue
        try:
            record = {
                "target": fields[0],
                "accession": fields[1],
                "query": fields[3],
                "full_evalue": float(fields[6]),
                "full_score": float(fields[7]),
                "evalue": float(fields[12]),
                "score": float(fields[13]),
                "hmm_from": int(fields[15]),
                "hmm_to": int(fields[16]),
                "ali_from": int(fields[17]),
                "ali_to": int(fields[18]),
                "env_from": int(fields[19]),
                "env_to": int(fields[20]),
            }
        except (ValueError, IndexError) as error:
            raise StepError(
                f"hmmer_domains: cannot parse a domtblout row: {line!r}"
            ) from error
        records.append(record)
    return records


def run_hmmscan(
    binary: Path,
    hmm: Path,
    sequences: list[str],
    *,
    cpu: int = 1,
    timeout: float = 1800.0,
) -> list[dict]:
    if not hmm.is_file():
        raise StepError(
            f"hmmer_domains: hmm_path '{hmm}' is not a file"
        )
    with tempfile.TemporaryDirectory(prefix="hmmscan_") as tmp:
        folder = Path(tmp)
        fasta = folder / "queries.faa"
        write_fasta(sequences, fasta)
        table = folder / "domains.domtbl"
        launcher = (
            [sys.executable, str(binary)]
            if str(binary).lower().endswith(".py")
            else [str(binary)]
        )
        command = [
            *launcher,
            "--domtblout",
            str(table),
            "--noali",
            "--cpu",
            str(max(1, int(cpu))),
            str(hmm),
            str(fasta),
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
                f"hmmer_domains: '{binary}' was not found on PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise StepError(
                f"hmmer_domains: hmmscan timed out after {timeout:.0f} s"
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError(
                "hmmer_domains: hmmscan failed with exit code "
                f"{completed.returncode}: {' | '.join(tail[-3:])}"
            )
        if not table.is_file():
            raise StepError("hmmer_domains: hmmscan produced no domtblout file")
        return parse_domtbl(table.read_text(encoding="utf-8", errors="replace"))



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

class HmmerDomainsStep(Step):
    provider = "operon-core"
    parameters_file = "hmmer_domains.HmmerDomainsStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "hmmer_domains",
        "version": "1.0.0",
        "kind": "operator",
        "title": "HMMER domain annotation",
        "category": "Sequence",
        "icon": "Database",
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
            "Annotate protein sequences with Pfam/HMMER domains through the "
            "official hmmscan binary and return one row per domain hit."
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
            raise StepError("hmmer_domains: the input carries no sequence")
        hmm_text = str(params.get("hmm_path", "") or "").strip() or os.environ.get(
            "OPERON_PFAM_HMM", ""
        )
        if not hmm_text:
            raise StepError(
                "hmmer_domains: hmm_path is required; set it to a pressed Pfam-A.hmm "
                "(see docs/large_resources.md for the download instructions)"
            )
        hmm = Path(hmm_text).expanduser()
        binary_text = str(params.get("hmmscan_path", "") or "").strip() or "hmmscan"
        records = run_hmmscan(
            Path(binary_text),
            hmm,
            sequences,
            cpu=int(params.get("cpu", 1)),
            timeout=float(params.get("timeout_seconds", 1800.0)),
        )
        if not records:
            raise StepError(
                "hmmer_domains: hmmscan reported no domain above the reporting "
                "threshold"
            )
        records.sort(key=lambda item: (item["evalue"], item["target"]))
        rows = [
            (
                record["evalue"],
                record["score"],
                record["hmm_from"],
                record["hmm_to"],
                record["ali_from"],
                record["ali_to"],
                record["env_from"],
                record["env_to"],
            )
            for record in records
        ]
        data = np.asarray(rows, dtype=np.float32)
        labels = {
            f"{record['target']}:{index + 1}": index
            for index, record in enumerate(records)
        }
        result = Form(
            data=data,
            dims=["domain", "statistic"],
            labels={
                "domain": labels,
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_domains": len(records),
                "n_targets": len({record["target"] for record in records}),
                "hmm_path": hmm.as_posix(),
                "queries": len(sequences),
                "domains": records,
            },
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return self._export_data
