"""sequence_rna_duplex: RNA-RNA hybridization through ViennaRNA RNAduplex."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

_LINE = re.compile(
    r"^(?P<structure>[.()&]+)\s+"
    r"(?P<a1>\d+),(?P<a2>\d+)\s*:\s*(?P<b1>\d+),(?P<b2>\d+)\s+"
    r"\((?P<energy>-?\d+(?:\.\d+)?)\)$"
)


def parse_duplex(text: str) -> list[dict]:
    """Parse RNAduplex output lines into duplex records."""

    records = []
    for line in text.splitlines():
        match = _LINE.match(line.strip())
        if match is None:
            continue
        records.append(
            {
                "structure": match.group("structure"),
                "start_a": int(match.group("a1")),
                "end_a": int(match.group("a2")),
                "start_b": int(match.group("b1")),
                "end_b": int(match.group("b2")),
                "energy": float(match.group("energy")),
            }
        )
    return records


def run_duplex(
    binary: str,
    sequences: tuple[str, str],
    *,
    energy_range: float = 0.0,
    timeout: int = 120,
) -> str:
    """Run RNAduplex for two RNA sequences and return its stdout."""

    if len(sequences) != 2:
        raise StepError(f"sequence_rna_duplex: expected exactly two sequences, got {len(sequences)}")
    cleaned = []
    for index, sequence in enumerate(sequences):
        text = str(sequence).upper().replace("T", "U")
        if not text:
            raise StepError(f"sequence_rna_duplex: sequence {index + 1} is empty")
        if set(text) - set("ACGUN"):
            raise StepError(f"sequence_rna_duplex: sequence {index + 1} contains non-RNA characters (expected ACGUN)")
        cleaned.append(text)
    workdir = Path(tempfile.mkdtemp(prefix="rnaduplex_"))
    command = [binary, "-e", str(max(float(energy_range), 0.1))]
    try:
        completed = subprocess.run(
            command,
            input="\n".join(cleaned) + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
    except FileNotFoundError:
        raise StepError(f"sequence_rna_duplex: RNAduplex executable '{binary}' was not found; install ViennaRNA") from None
    except subprocess.TimeoutExpired:
        raise StepError(f"sequence_rna_duplex: RNAduplex timed out after {timeout} s") from None
    if completed.returncode != 0:
        tail = ((completed.stderr or completed.stdout).strip().splitlines() or [""])[-1]
        raise StepError(f"sequence_rna_duplex: RNAduplex failed with exit code {completed.returncode}: {tail}")
    return completed.stdout


class SequenceRnaDuplexStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_rna_duplex.SequenceRnaDuplexStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_rna_duplex",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA-RNA 杂交位点",
        "description": (
            "Compute the optimal and near-optimal hybridization sites between two RNA "
            "sequences with ViennaRNA RNAduplex and report the duplex energy and spans."
        ),
        "category": "Sequence",
        "icon": "Scissors",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sequence_dim"}, {"param": "position_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": [],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequences = decode_sequences(inputs[0], str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        text = run_duplex(
            str(params.get("rnaduplex_path", "RNAduplex")),
            (sequences[0], sequences[1]),
            energy_range=float(params.get("energy_range", 0.0)),
            timeout=int(params.get("timeout_seconds", 120)),
        )
        records = parse_duplex(text)
        if not records:
            raise StepError("sequence_rna_duplex: RNAduplex reported no duplex")
        records.sort(key=lambda item: (item["energy"], item["start_a"]))
        values = np.asarray(
            [[row["start_a"], row["end_a"], row["start_b"], row["end_b"], row["energy"]] for row in records],
            dtype=np.float32,
        )
        out_dim = str(params.get("duplex_dim", "duplex"))
        out_name = str(params.get("output", "duplexes"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {f"duplex{index + 1}": index for index in range(len(records))},
                "statistic": {"start_a": 0, "end_a": 1, "start_b": 2, "end_b": 3, "energy": 4},
            },
            info={
                "missing_code": np.nan,
                "n_duplexes": len(records),
                "best_energy": records[0]["energy"],
                "best_structure": records[0]["structure"],
                "sequences": list(sequences),
                "energy_range": float(params.get("energy_range", 0.0)),
            },
        )
        self._export_data = {"duplexes": records[:50], "best_energy": records[0]["energy"]}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
