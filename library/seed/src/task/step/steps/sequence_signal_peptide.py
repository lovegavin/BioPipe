"""Heuristic signal-peptide detection for protein sequences."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.sequence_hydrophobicity_profile import KYTE_DOOLITTLE

_SMALL = frozenset("AGSTCPV")
_POSITIVE = frozenset("KR")
_NEGATIVE = frozenset("DE")


def hydropathy(sequence: str, operator: str = "sequence_signal_peptide") -> np.ndarray:
    """Kyte-Doolittle hydropathy, rejecting non-standard residues."""

    unknown = sorted({residue for residue in sequence if residue not in KYTE_DOOLITTLE})
    if unknown:
        raise StepError(
            f"{operator}: residues outside the Kyte-Doolittle scale: {''.join(unknown)}"
        )
    return np.asarray([KYTE_DOOLITTLE[residue] for residue in sequence], dtype=np.float64)


def net_charge(region: str) -> int:
    """Net lysine/arginine minus aspartate/glutamate charge of an n-region."""

    return sum(residue in _POSITIVE for residue in region) - sum(
        residue in _NEGATIVE for residue in region
    )


def signal_peptide(
    sequence: str,
    *,
    max_length: int = 40,
    min_hydrophobicity: float = 1.0,
    require_positive_n: bool = True,
) -> dict:
    """Best signal-peptide hypothesis for one sequence.

    A candidate cleavage site ``c`` (1-based, the last h-region residue) is
    accepted when a 7-15 residue hydrophobic window ends at ``c - 1``, the
    ``-1`` position is a small residue, and the n-region is not negatively
    charged. The reported score rewards a hydrophobic h-region, small ``-1``
    and ``-3`` residues and a non-negative n-region charge.
    """

    sequence = sequence.strip().upper()
    if not sequence:
        raise StepError("sequence_signal_peptide: the sequence is empty")
    values = hydropathy(sequence)
    limit = min(max_length, len(sequence) - 2)
    best: dict | None = None
    for site in range(15, limit + 1):
        end = site - 1
        for length in range(15, 6, -1):
            start = end - length
            if start < 0:
                continue
            h_mean = float(values[start:end].mean())
            if h_mean < min_hydrophobicity:
                continue
            small_minus_one = sequence[site - 1] in _SMALL
            if not small_minus_one:
                continue
            small_minus_three = sequence[site - 3] in _SMALL
            charge = net_charge(sequence[:start])
            if require_positive_n and charge < 0:
                continue
            score = h_mean + (0.5 if small_minus_one else 0.0) + (0.5 if small_minus_three else 0.0) + 0.2 * np.sign(charge)
            candidate = {
                "cleavage_site": site,
                "h_start": start + 1,
                "h_end": end,
                "h_length": length,
                "h_mean": h_mean,
                "n_charge": charge,
                "small_minus_one": small_minus_one,
                "small_minus_three": small_minus_three,
                "score": float(score),
                "n_region": sequence[:start],
                "h_region": sequence[start:end],
                "c_region": sequence[end:end + 3],
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
            break
    if best is None:
        return {
            "detected": False,
            "cleavage_site": 0,
            "h_start": 0,
            "h_end": 0,
            "h_length": 0,
            "h_mean": float("nan"),
            "n_charge": 0,
            "score": 0.0,
            "n_region": "",
            "h_region": "",
            "c_region": "",
        }
    best["detected"] = True
    return best


_STATISTICS = (
    "cleavage_site",
    "h_start",
    "h_end",
    "h_mean",
    "n_charge",
    "score",
    "detected",
)


class SequenceSignalPeptideStep(Step):
    """Detect secretory signal peptides with a SignalP-style heuristic."""

    provider = "operon-core"

    parameters_file = "sequence_signal_peptide.SequenceSignalPeptideStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_signal_peptide",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Signal peptide detection",
        "description": (
            "Detect an N-terminal signal peptide with a SignalP-style heuristic: a "
            "positively charged n-region, a 7-15 residue hydrophobic h-region, a small "
            "residue at the -1 and -3 positions and a reported cleavage site."
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
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        params = ctx.step_params
        (sequences,) = inputs
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        out_name = str(params.get("output") or "signal")
        max_length = int(params.get("max_length") or 40)
        min_hydrophobicity = float(params.get("min_hydrophobicity") or 1.0)
        require_positive_n = bool(params.get("require_positive_n", True))
        if not 15 <= max_length <= 60:
            raise StepError("sequence_signal_peptide: max_length must be between 15 and 60")
        if not -2.0 <= min_hydrophobicity <= 5.0:
            raise StepError(
                "sequence_signal_peptide: min_hydrophobicity must be between -2 and 5"
            )

        decoded = decode_sequences(sequences, sequence_dim, position_dim)
        if not decoded:
            raise StepError("sequence_signal_peptide: the input holds no sequences")
        names = sorted(sequences.labels[sequence_dim].items(), key=lambda item: item[1])
        results = []
        for index, sequence in enumerate(decoded):
            result = signal_peptide(
                sequence,
                max_length=max_length,
                min_hydrophobicity=min_hydrophobicity,
                require_positive_n=require_positive_n,
            )
            result["label"] = str(names[index][0]) if index < len(names) else f"seq{index + 1}"
            results.append(result)

        data = np.asarray(
            [
                [
                    result["cleavage_site"],
                    result["h_start"],
                    result["h_end"],
                    result["h_mean"],
                    result["n_charge"],
                    result["score"],
                    1.0 if result["detected"] else 0.0,
                ]
                for result in results
            ],
            dtype=np.float32,
        )
        form = Form(
            data,
            dims=["peptide", "statistic"],
            labels={
                "peptide": {result["label"]: index for index, result in enumerate(results)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(results),
                "n_detected": sum(1 for result in results if result["detected"]),
                "max_length": max_length,
                "min_hydrophobicity": min_hydrophobicity,
                "require_positive_n": require_positive_n,
                "cleavage_sites": [result["cleavage_site"] for result in results],
                "h_regions": [result["h_region"] for result in results],
            },
        )
        ctx[out_name] = form
        self._export_data = form

    def export(self, ctx) -> dict:
        form = self._export_data
        return {
            "operator": "sequence_signal_peptide",
            "n_sequences": int(form.info["n_sequences"]),
            "n_detected": int(form.info["n_detected"]),
        }
