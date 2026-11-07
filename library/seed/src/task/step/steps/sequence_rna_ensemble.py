"""sequence_rna_ensemble: RNA ensemble statistics with ViennaRNA."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.sequence_rna_fold import clean_sequence

_SEQ_LINE = re.compile(r"^\(([.()\[\]{}<>A-Za-z]+)\)\s*\(\s*(-?\d+\.\d+)\)\s*$")
_ENS_LINE = re.compile(r"^\(([.()\[\]{}<>A-Za-z]+)\)\s*\[\s*(-?\d+\.\d+)\]\s*$")
_MEA_LINE = re.compile(r"^\(([.()\[\]{}<>A-Za-z]+)\)\s*\{\s*(-?\d+\.\d+)\s+d=\s*(-?\d+\.\d+)\}\s*$")
_FREQ_LINE = re.compile(r"frequency of mfe structure in ensemble\s+([0-9.]+);\s*ensemble diversity\s+([0-9.]+)")


def _numbers(text: str) -> list[float]:
    return [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", text)]


def parse_ensemble_output(text: str, operator: str) -> list[dict]:
    """Parse the ``RNAfold -p`` stdout into one record per sequence."""

    records: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"[ACGUTN]+", line):
            current = {"sequence": line.upper()}
            records.append(current)
            continue
        if current is None:
            continue
        if line.endswith("}"):
            structure, payload = line.rsplit("{", 1)
            values = _numbers(payload)
            current["mea_structure"] = structure.strip()
            if values:
                current["mea_energy"] = values[0]
            if len(values) > 1:
                current["mea_diversity"] = values[1]
            continue
        if line.endswith("]"):
            structure, payload = line.rsplit("[", 1)
            values = _numbers(payload)
            current["ensemble_structure"] = structure.strip()
            if values:
                current["ensemble"] = values[0]
            continue
        if line.endswith(")") and "(" in line:
            structure, payload = line.rsplit(" (", 1)
            values = _numbers(payload)
            if len(values) == 1:
                current["mfe_structure"] = structure.strip()
                current["mfe"] = values[0]
                continue
        match = _FREQ_LINE.search(line)
        if match:
            current["mfe_frequency"] = float(match.group(1))
            current["ensemble_diversity"] = float(match.group(2))
            continue
    complete = [
        record
        for record in records
        if all(key in record for key in ("mfe", "ensemble", "mea_energy", "mfe_frequency"))
    ]
    if not complete:
        raise StepError(f"{operator}: no ensemble statistics could be parsed from the RNAfold output")
    for record in complete:
        structure = record.get("mfe_structure", "")
        record["n_pairs"] = sum(1 for char in structure if char in "([{<")
    return complete


def run_rnafold_ensemble(
    sequences: list[str],
    *,
    binary: str = "RNAfold",
    temperature: float = 37.0,
    dangles: int = 2,
    timeout: int = 600,
) -> list[dict]:
    """Run ``RNAfold -p`` and return the per-sequence ensemble statistics."""

    from shutil import which

    resolved = binary if Path(binary).is_file() else which(binary)
    if not resolved:
        raise StepError(f"sequence_rna_ensemble: '{binary}' was not found on PATH")
    command = [str(resolved), "-p", "--noPS", "-T", f"{float(temperature):.1f}", "-d", str(int(dangles))]
    payload = "\n".join(sequences) + "\n"
    try:
        completed = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise StepError(f"sequence_rna_ensemble: RNAfold timed out after {timeout} s") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-2:]
        raise StepError(f"sequence_rna_ensemble: RNAfold failed with exit code {completed.returncode}: {' | '.join(tail)}")
    return parse_ensemble_output(completed.stdout, "sequence_rna_ensemble")


class SequenceRnaEnsembleStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_rna_ensemble.SequenceRnaEnsembleStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_rna_ensemble",
        "version": "1.0.0",
        "kind": "operator",
        "title": "RNA 系综统计 (RNAfold -p)",
        "description": (
            "Run the ViennaRNA partition function (RNAfold -p) and report the MFE energy, "
            "ensemble free energy, maximum expected accuracy structure and energy, the "
            "frequency of the MFE structure and the ensemble diversity."
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
            raise StepError("sequence_rna_ensemble: the input form is empty")
        raw = decode_sequences(form, str(params.get("sequence_dim", "sequence")), str(params.get("position_dim", "position")))
        sequences = [clean_sequence(sequence, "sequence_rna_ensemble") for sequence in raw]
        records = run_rnafold_ensemble(
            sequences,
            binary=str(params.get("rnafold_path", "RNAfold")),
            temperature=float(params.get("temperature", 37.0)),
            dangles=int(params.get("dangles", 2)),
            timeout=int(params.get("timeout_seconds", 600)),
        )
        statistics = ("mfe", "ensemble", "mea_energy", "mea_diversity", "mfe_frequency", "ensemble_diversity", "n_pairs")
        values = np.asarray([[row[stat] for stat in statistics] for row in records], dtype=np.float32)
        out_dim = str(params.get("sequence_output_dim", "sequence"))
        out_name = str(params.get("output", "ensembles"))
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
                "mean_ensemble": float(np.mean([row["ensemble"] for row in records])),
                "mfe_structures": [row.get("mfe_structure", "") for row in records],
                "mea_structures": [row.get("mea_structure", "") for row in records],
                "sequences": sequences,
                "temperature": float(params.get("temperature", 37.0)),
            },
        )
        self._export_data = {"records": records, "n_sequences": len(records)}

    def export(self, ctx):
        return getattr(self, "_export_data", {})
