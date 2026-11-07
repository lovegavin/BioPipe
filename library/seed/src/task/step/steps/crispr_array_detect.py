"""CRISPR array detection through the official minced tool."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_COLUMNS = ("start", "end", "length", "n_repeats", "repeat_length", "spacer_length")
_HEADER = re.compile(r"^CRISPR\s+(\d+)\s+Range:\s*(\d+)\s*-\s*(\d+)", re.IGNORECASE)
_ROW = re.compile(
    r"^(\d+)\s+([ACGTNacgtn]+)\s+([ACGTNacgtn]+)\s+\[\s*(\d+)\s*,\s*(\d+)\s*\]"
)
# minced prints the terminal repeat without a spacer and without the
# ``[repeat, spacer]`` block; keep it so the repeat count matches the report.
_TERMINAL = re.compile(r"^(\d+)\s+([ACGTNacgtn]+)\s*$")


def write_fasta(sequences: list[str], path: Path) -> None:
    lines: list[str] = []
    for index, sequence in enumerate(sequences):
        lines.append(f">sequence{index + 1}")
        for start in range(0, len(sequence), 70):
            lines.append(sequence[start : start + 70])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def tool_environment(binary: str) -> dict:
    """prepend the tool directory so minced can exec its bundled ``java``."""

    env = dict(os.environ)
    folder = str(Path(binary).expanduser().absolute().parent)
    env["PATH"] = folder + os.pathsep + env.get("PATH", "")
    return env


def parse_crisprs(text: str, sequence_names: list[str]) -> list[dict]:
    """Parse minced's ``.crisprs`` text into array records."""

    arrays: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        header = _HEADER.match(line.strip())
        if header:
            current = {
                "array": int(header.group(1)),
                "start": int(header.group(2)),
                "end": int(header.group(3)),
                "rows": [],
            }
            arrays.append(current)
            continue
        if current is None:
            continue
        row = _ROW.match(line.strip())
        if row:
            current["rows"].append(
                {
                    "position": int(row.group(1)),
                    "repeat": row.group(2).upper(),
                    "spacer": row.group(3).upper(),
                    "repeat_length": int(row.group(4)),
                    "spacer_length": int(row.group(5)),
                }
            )
            continue
        terminal = _TERMINAL.match(line.strip())
        if terminal:
            current["rows"].append(
                {
                    "position": int(terminal.group(1)),
                    "repeat": terminal.group(2).upper(),
                    "spacer": "",
                    "repeat_length": 0,
                    "spacer_length": 0,
                }
            )
    for index, array in enumerate(arrays):
        rows = array.pop("rows")
        repeat_length = next(
            (row["repeat_length"] for row in rows if row["repeat_length"]), 0
        )
        spacer_length = next(
            (row["spacer_length"] for row in rows if row["spacer_length"]), 0
        )
        for row in rows:
            if not row["repeat_length"]:
                row["repeat_length"] = repeat_length
            if not row["spacer_length"]:
                row["spacer_length"] = spacer_length
        array["sequence"] = sequence_names[0] if sequence_names else ""
        array["n_repeats"] = len(rows)
        array["length"] = array["end"] - array["start"] + 1
        array["repeat_length"] = repeat_length
        array["spacer_length"] = spacer_length
        repeats = [row["repeat"] for row in rows if row["repeat"]]
        array["consensus_repeat"] = (
            Counter(repeats).most_common(1)[0][0] if repeats else ""
        )
        array["positions"] = [row["position"] for row in rows]
        array["matches"] = len(rows)
        array["index"] = index
    return arrays


def run_minced(
    binary: str,
    sequences: list[str],
    *,
    min_repeats: int = 3,
    timeout: float = 300.0,
) -> list[dict]:
    """Run minced on the sequences and return parsed arrays."""

    with tempfile.TemporaryDirectory(prefix="minced_") as tmp:
        folder = Path(tmp)
        fasta = folder / "input.fna"
        write_fasta(sequences, fasta)
        output = folder / "arrays.crisprs"
        launcher = (
            [sys.executable, binary]
            if str(binary).lower().endswith(".py")
            else [binary]
        )
        command = [
            *launcher,
            "-minNR",
            str(max(1, int(min_repeats))),
            str(fasta),
            str(output),
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
            raise StepError(f"crispr_array_detect: '{binary}' was not found") from error
        except subprocess.TimeoutExpired as error:
            raise StepError(
                f"crispr_array_detect: minced timed out after {timeout:.0f} s"
            ) from error
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            raise StepError(
                "crispr_array_detect: minced failed with exit code "
                f"{completed.returncode}: {' | '.join(tail[-3:])}"
            )
        text = (
            output.read_text(encoding="utf-8", errors="replace")
            if output.is_file()
            else ""
        )
        names = [f"sequence{index + 1}" for index in range(len(sequences))]
        arrays = parse_crisprs(text, names)
    return arrays


class CrisprArrayDetectStep(Step):
    provider = "operon-core"
    parameters_file = "crispr_array_detect.CrisprArrayDetectStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "crispr_array_detect",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CRISPR array detection",
        "description": (
            "Detect CRISPR arrays with the official minced tool and report repeat "
            "counts, repeat/spacer lengths and consensus repeats."
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
            "external_tools": ["minced"],
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
            raise StepError("crispr_array_detect: the input carries no sequence")
        binary = str(params.get("minced_path") or "minced")
        resolved = shutil.which(binary) or (binary if Path(binary).is_file() else "")
        if not resolved:
            raise StepError(
                "crispr_array_detect: the minced executable was not found; set "
                "minced_path to its location"
            )
        arrays = run_minced(
            resolved,
            sequences,
            min_repeats=int(params.get("min_repeats", 3)),
            timeout=float(params.get("timeout_seconds", 300)),
        )
        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        for array in arrays:
            name = f"array={array['array']}"
            labels[name] = len(rows)
            rows.append([float(array[column]) for column in _COLUMNS])
        data = (
            np.asarray(rows, dtype=np.float32)
            if rows
            else np.zeros((0, len(_COLUMNS)), dtype=np.float32)
        )
        ctx[out_name] = Form(
            data=data,
            dims=["array", "statistic"],
            labels={
                "array": labels,
                "statistic": {name: index for index, name in enumerate(_COLUMNS)},
            },
            info={
                "missing_code": np.nan,
                "source": "minced",
                "n_arrays": len(arrays),
                "arrays": arrays,
            },
        )
        self._export_data = {
            "output": out_name,
            "n_arrays": len(arrays),
            "arrays": [
                {
                    "start": array["start"],
                    "end": array["end"],
                    "n_repeats": array["n_repeats"],
                    "consensus_repeat": array["consensus_repeat"],
                }
                for array in arrays
            ],
        }

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
