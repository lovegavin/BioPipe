"""tRNA gene detection through the official tRNAscan-SE binary."""

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


def _tool_env(binary: Path) -> dict:
    """Make helper binaries from the tool's own environment visible."""
    env = dict(os.environ)
    env["PATH"] = str(Path(binary).resolve().parent) + os.pathsep + env.get("PATH", "")
    return env

_STATISTICS = ("start", "end", "length", "score", "intron_start", "intron_end")
_MODES = {"general": "-G", "bacterial": "-B", "archaeal": "-A", "eukaryotic": "-E"}


def write_fasta(sequences: list[str], path: Path) -> None:
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f">query{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_output(text: str) -> list[dict]:
    """Parse the tRNAscan-SE tabular report into tRNA records."""

    trnas: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("-") or line.startswith("Sequence"):
            continue
        if line.startswith("Name") or line.startswith("tRNA"):
            continue
        fields = line.split()
        if len(fields) < 9:
            continue
        try:
            trna = {
                "query": fields[0],
                "index": int(fields[1]),
                "start": int(fields[2]),
                "end": int(fields[3]),
                "isotype": fields[4],
                "anticodon": fields[5],
                "intron_start": int(fields[6]),
                "intron_end": int(fields[7]),
                "score": float(fields[8]),
                "note": " ".join(fields[9:]),
            }
        except (ValueError, IndexError) as error:
            raise StepError(f"trnascan_se: cannot parse a tRNAscan-SE row: {line!r}") from error
        trnas.append(trna)
    return trnas


def run_trnascan(binary: Path, sequences: list[str], *, mode: str = "general",
                 timeout: float = 900.0) -> list[dict]:
    if mode not in _MODES:
        raise StepError(f"trnascan_se: mode must be one of {', '.join(_MODES)}")
    with tempfile.TemporaryDirectory(prefix="trnascan_") as tmp:
        folder = Path(tmp)
        fasta = folder / "queries.fa"
        write_fasta(sequences, fasta)
        output = folder / "trnas.txt"
        launcher = [sys.executable, str(binary)] if str(binary).lower().endswith(".py") else [str(binary)]
        command = [*launcher, "-q", _MODES[mode], "-o", str(output), str(fasta)]
        try:
            completed = subprocess.run(command, check=False, capture_output=True,
                                       text=True, timeout=timeout, env=_tool_env(binary))
        except FileNotFoundError as error:
            raise StepError(f"trnascan_se: '{binary}' was not found on PATH") from error
        except subprocess.TimeoutExpired as error:
            raise StepError(f"trnascan_se: tRNAscan-SE timed out after {timeout:.0f} s") from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError("trnascan_se: tRNAscan-SE failed with exit code "
                            f"{completed.returncode}: {' | '.join(tail[-3:])}")
        if not output.is_file():
            raise StepError("trnascan_se: tRNAscan-SE produced no report")
        return parse_output(output.read_text(encoding="utf-8", errors="replace"))


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


class TrnascanSeStep(Step):
    provider = "operon-core"
    parameters_file = "trnascan_se.TrnascanSeStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "trnascan_se",
        "version": "1.0.0",
        "kind": "operator",
        "title": "tRNAscan-SE tRNA genes",
        "category": "Genome",
        "icon": "Dna",
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
                      "external_tools": ["tRNAscan-SE"]},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Detect tRNA genes with the official tRNAscan-SE binary; returns "
            "coordinates, isotype, anticodon, intron bounds and score."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")),
                                     str(params.get("position_dim", "position")))
        if not sequences:
            raise StepError("trnascan_se: the input carries no sequence")
        binary = Path(str(params.get("trnascan_path", "") or "tRNAscan-SE")).expanduser()
        trnas = run_trnascan(binary, sequences,
                             mode=str(params.get("mode", "general") or "general"),
                             timeout=float(params.get("timeout_seconds", 900.0)))
        rows = [(trna["start"], trna["end"], trna["end"] - trna["start"] + 1,
                 trna["score"], trna["intron_start"], trna["intron_end"]) for trna in trnas]
        data = np.asarray(rows, dtype=np.float32).reshape(len(rows), len(_STATISTICS))
        labels = {f"{trna['query']}:{trna['index']}": index for index, trna in enumerate(trnas)}
        result = Form(
            data=data,
            dims=["trna", "statistic"],
            labels={"trna": labels,
                    "statistic": {name: index for index, name in enumerate(_STATISTICS)}},
            info={"missing_code": np.nan, "trnas": trnas, "n_trnas": len(trnas),
                  "isotypes": sorted({trna["isotype"] for trna in trnas}),
                  "mode": str(params.get("mode", "general"))},
        )
        self._export_data = _export_summary(result)
        ctx[out_name] = result

    def export(self, ctx: Context):
        return getattr(self, "_export_data", {})
