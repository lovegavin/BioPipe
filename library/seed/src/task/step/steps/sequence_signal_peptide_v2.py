"""Signal-peptide type and cleavage-site scan (Sec/SPI, Tat, lipoprotein)."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.sequence_hydrophobicity_profile import KYTE_DOOLITTLE

_SMALL = frozenset("AGSTCPVND")
_STATISTICS = ("detected", "cleavage_site", "h_start", "h_end", "h_mean", "score", "type_code")
_TYPES = ("none", "Sec/SPI", "Tat/SPI", "Sec/SPII", "Tat/SPII")


def hydropathy(sequence: str, operator: str = "sequence_signal_peptide_v2") -> np.ndarray:
    values = []
    for residue in sequence:
        if residue not in KYTE_DOOLITTLE:
            raise StepError(f"{operator}: residue '{residue}' is outside the Kyte-Doolittle scale")
        values.append(KYTE_DOOLITTLE[residue])
    return np.asarray(values, dtype=np.float64)


def tat_motif(region: str) -> bool:
    return "RR" in region or "KR" in region


def type_code(tat: bool, lipoprotein: bool) -> int:
    if lipoprotein:
        return 4 if tat else 3
    return 2 if tat else 1


def scan_signal_peptide(
    sequence: str,
    *,
    min_hydrophobicity: float = 0.9,
    min_h_length: int = 7,
    max_h_length: int = 15,
) -> dict:
    """Return the best signal-peptide hypothesis for one sequence."""

    sequence = str(sequence or "").strip().upper()
    if not sequence:
        raise StepError("sequence_signal_peptide_v2: the input carries an empty sequence")
    profile = hydropathy(sequence)
    length = len(sequence)
    best: dict | None = None
    for start in range(0, min(25, max(0, length - 20))):
        for h_length in range(min_h_length, max_h_length + 1):
            end = start + h_length
            if end + 2 >= length:
                break
            h_mean = float(profile[start:end].mean())
            if h_mean < min_hydrophobicity:
                continue
            region = sequence[start:end]
            tat = tat_motif(sequence[max(0, start - 2) : end])
            for site in range(end + 1, min(end + 8, length - 1)):
                minus_one = sequence[site - 1]
                minus_three = sequence[site - 3] if site >= 3 else ""
                if minus_one not in _SMALL:
                    continue
                small_score = 0.30 * (minus_three in _SMALL)
                lipoprotein = sequence[site] == "C"
                score = h_mean + 0.5 * small_score + (0.2 if tat else 0.0)
                candidate = {
                    "detected": 1,
                    "cleavage_site": site,
                    "h_start": start + 1,
                    "h_end": end,
                    "h_mean": h_mean,
                    "score": score,
                    "type_code": type_code(tat, lipoprotein),
                    "type": _TYPES[type_code(tat, lipoprotein)],
                    "n_region": sequence[:start],
                    "h_region": region,
                }
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
    if best is None:
        return {
            "detected": 0,
            "cleavage_site": 0,
            "h_start": 0,
            "h_end": 0,
            "h_mean": float("nan"),
            "score": 0.0,
            "type_code": 0,
            "type": "none",
            "n_region": "",
            "h_region": "",
        }
    return best


def signal_rows(sequences, **kwargs) -> list[dict]:
    return [scan_signal_peptide(sequence, **kwargs) for sequence in sequences]


class SequenceSignalPeptideV2Step(Step):
    """Classify signal peptides as Sec/Tat and secretory/lipoprotein."""

    provider = "operon-core"
    parameters_file = "sequence_signal_peptide_v2.SequenceSignalPeptideV2Step.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_signal_peptide_v2",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Signal peptide typing",
        "description": (
            "Scan a protein sequence for a signal peptide, discriminate secretory "
            "from Tat-dependent and lipoprotein from non-lipoprotein routes, and "
            "report the most likely signal peptidase cleavage site."
        ),
        "category": "Sequence",
        "icon": "Scissors",
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
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet_map": {"type": "object", "optional": True},
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
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")) or "sequence"
        position_dim = str(params.get("position_dim", "position")) or "position"
        peptide_dim = str(params.get("peptide_dim", "peptide")) or "peptide"
        out_name = str(params.get("output", "signals")) or "signals"
        sequences = decode_sequences(inputs[0], sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_signal_peptide_v2: the input carries no sequence")
        rows = signal_rows(
            sequences,
            min_hydrophobicity=float(params.get("min_hydrophobicity", 0.9)),
        )
        detected = [row for row in rows if row["detected"]]
        if not detected:
            raise StepError(
                "sequence_signal_peptide_v2: no sequence carries a detectable signal peptide"
            )
        labels = {
            peptide_dim: {f"seq{index + 1}": index for index in range(len(rows))},
            "statistic": {name: index for index, name in enumerate(_STATISTICS)},
        }
        data = np.zeros((len(rows), len(_STATISTICS)), dtype=np.float32)
        for index, row in enumerate(rows):
            data[index] = (
                row["detected"],
                row["cleavage_site"],
                row["h_start"],
                row["h_end"],
                float("nan") if not np.isfinite(row["h_mean"]) else row["h_mean"],
                row["score"],
                row["type_code"],
            )
        ctx[out_name] = Form(
            data=data,
            dims=[peptide_dim, "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_sequences": len(rows),
                "n_detected": len(detected),
                "types": [row["type"] for row in rows],
                "cleavage_sites": [row["cleavage_site"] for row in rows],
                "h_regions": [row["h_region"] for row in rows],
                "n_regions": [row["n_region"] for row in rows],
            },
        )
        self._export_data = {
            "n_sequences": len(rows),
            "n_detected": len(detected),
            "types": [row["type"] for row in rows],
            "cleavage_sites": [row["cleavage_site"] for row in rows],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
