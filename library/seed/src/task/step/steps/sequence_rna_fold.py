"""sequence_rna_fold: RNA secondary structure with ViennaRNA."""

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

_ALLOWED = set("ACGUTN")
_RESULT = re.compile(r"^([.()\[\]{}<>A-Za-z]+)\s+\(\s*(-?\d+\.\d+)\)(?:\s+\[\s*(-?\d+\.\d+)\])?\s*$")
_ENSEMBLE = re.compile(r"^([.()\[\]{}<>A-Za-z]+)\s+\[\s*(-?\d+\.\d+)\s*\]")


def clean_sequence(sequence: str, operator: str) -> str:
    """Normalise an RNA sequence, rejecting anything that is not nucleotide."""

    text = "".join(str(sequence).split()).upper().replace("T", "U")
    if not text:
        raise StepError(f"{operator}: the sequence is empty")
    invalid = sorted({char for char in text if char not in _ALLOWED})
    if invalid:
        raise StepError(f"{operator}: sequence contains non-nucleotide characters {invalid}")
    return text


def parse_output(text: str, operator: str) -> list[dict]:
    """Parse RNAfold stdout into one record per sequence."""

    records = []
    lines = [line for line in text.splitlines() if line.strip()]
    index = 0
    while index < len(lines):
        header = lines[index].strip()
        if "(" not in header and index + 1 < len(lines):
            match = _RESULT.match(lines[index + 1].strip())
            if match:
                structure = match.group(1).strip()
                mfe = float(match.group(2))
                ensemble = float(match.group(3)) if match.group(3) is not None else float("nan")
                if index + 2 < len(lines):
                    follow = _ENSEMBLE.match(lines[index + 2].strip())
                    if follow and follow.group(1).strip() == structure:
                        ensemble = float(follow.group(2))
                pairs = sum(1 for char in structure if char in "([{<")
                records.append(
                    {
                        "sequence": header.upper(),
                        "structure": structure,
                        "mfe": mfe,
                        "ensemble": ensemble,
                        "n_pairs": pairs,
                        "gc": (header.upper().count("G") + header.upper().count("C")) / max(len(header), 1),
                    }
                )
                index += 2
                continue
        index += 1
    if not records:
        raise StepError(f"{operator}: no structure could be parsed from the RNAfold output")
    return records


def run_rnafold(
    sequences: list[str],
    *,
    binary: str = "RNAfold",
    temperature: float = 37.0,
    dangles: int = 2,
    no_lonely_pairs: bool = False,
    timeout: int = 600,
) -> list[dict]:
    """Run the official RNAfold binary on a list of sequences."""

    from shutil import which

    resolved = binary if Path(binary).is_file() else which(binary)
    if not resolved:
        raise StepError(f"sequence_rna_fold: '{binary}' was not found on PATH")
    command = [str(resolved), "--noPS", "-p", "-T", f"{float(temperature):.1f}", "-d", str(int(dangles))]
    if no_lonely_pairs:
        command.append("--noLP")
    payload = "\n".join(sequences) + "\n"
    try:
        completed = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"sequence_rna_fold: RNAfold timed out after {timeout} s") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-2:]
        raise StepError(f"sequence_rna_fold: RNAfold failed with exit code {completed.returncode}: {' | '.join(tail)}")
    return parse_output(completed.stdout, "sequence_rna_fold")


class SequenceRnaFoldStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_rna_fold.SequenceRnaFoldStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_rna_fold",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 二级结构折叠 (ViennaRNA)",
        "description": (
            "Fold RNA sequences with the official ViennaRNA RNAfold implementation and "
            "report the minimum free energy structure, energy, ensemble energy, base-pair "
            "count and GC content."
        ),
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
                }
            ],
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
        form = inputs[0]
        if not isinstance(form, Form) or form.data.size == 0:
            raise StepError("sequence_rna_fold: the input form is empty")
        raw = decode_sequences(form, str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        sequences = [clean_sequence(sequence, "sequence_rna_fold") for sequence in raw]
        records = run_rnafold(
            sequences,
            binary=str(params.get("rnafold_path", "RNAfold")),
            temperature=float(params.get("temperature", 37.0)),
            dangles=int(params.get("dangles", 2)),
            no_lonely_pairs=bool(params.get("no_lonely_pairs", False)),
            timeout=int(params.get("timeout_seconds", 600)),
        )
        statistics = ("mfe", "ensemble", "n_pairs", "gc", "length")
        values = np.asarray(
            [[row["mfe"], row["ensemble"], row["n_pairs"], row["gc"], len(row["sequence"])] for row in records],
            dtype=np.float32,
        )
        out_dim = str(params.get("sequence_output_dim", "sequence"))
        out_name = str(params.get("output", "folds"))
        ctx[out_name] = Form(
            data=values,
            dims=[out_dim, "statistic"],
            labels={
                out_dim: {f"seq{index + 1}": index for index in range(len(records))},
                "statistic": {stat: index for index, stat in enumerate(statistics)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(records),
                "mean_mfe": float(np.mean([row["mfe"] for row in records])),
                "structures": [row["structure"] for row in records],
                "sequences": sequences,
                "temperature": float(params.get("temperature", 37.0)),
            },
        )
        self._export_data = {"records": records, "n_sequences": len(records)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
