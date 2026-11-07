"""Codon adaptation index (CAI) of coding sequences.

The CAI (Sharp & Li, 1987) is the geometric mean of the relative adaptiveness
``w`` of every codon in a target coding sequence, where ``w`` comes from the
codon counts of a reference coding set.  The definition follows Biopython's
``Bio.SeqUtils.CodonAdaptationIndex``: codons absent from the reference get the
paper's 0.5 pseudo-count, ATG and TGG are excluded from the mean, and stop
codons are included only when the reference defines them.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import CODON_TABLE, decode_sequences

_STATISTICS = ("cai", "n_codons", "n_excluded", "frac_optimal")
_SINGLETON_CODONS = frozenset({"ATG", "TGG"})
_ABSENT_WEIGHT = 0.5


def _sequence_names(form: Form, dimension: str) -> list[str]:
    labels = form.labels.get(dimension, {})
    ordered = sorted(labels.items(), key=lambda item: item[1])
    return [str(label) for label, _ in ordered]


def _validated(sequences: list[str], role: str) -> list[str]:
    if not sequences:
        raise StepError(f"sequence_codon_adaptation: no {role} sequences were provided")
    out: list[str] = []
    for index, sequence in enumerate(sequences):
        text = sequence.upper()
        if not text:
            raise StepError(
                f"sequence_codon_adaptation: {role} sequence {index + 1} is empty"
            )
        bad = sorted({char for char in text if char not in "ACGT"})
        if bad:
            raise StepError(
                f"sequence_codon_adaptation: {role} sequence {index + 1} contains "
                f"non-ACGT characters {bad}"
            )
        if len(text) % 3 != 0:
            raise StepError(
                f"sequence_codon_adaptation: {role} sequence {index + 1} length "
                f"{len(text)} is not a multiple of three"
            )
        out.append(text)
    return out


def codon_weights(
    reference_sequences: list[str], absent_weight: float = _ABSENT_WEIGHT
) -> dict[str, float]:
    """Relative adaptiveness of every codon from a reference coding set."""

    counts = {c1 + c2 + c3: 0 for c1 in "ACGT" for c2 in "ACGT" for c3 in "ACGT"}
    for sequence in reference_sequences:
        for start in range(0, len(sequence), 3):
            counts[sequence[start : start + 3]] += 1

    groups: dict[str, list[str]] = {}
    for codon, amino_acid in CODON_TABLE.items():
        groups.setdefault(amino_acid, []).append(codon)

    weights: dict[str, float] = {}
    for codons in groups.values():
        values = {
            codon: float(counts[codon]) if counts[codon] else float(absent_weight)
            for codon in codons
        }
        denominator = max(values.values())
        for codon, value in values.items():
            weights[codon] = value / denominator
    return weights


def adaptation_index(
    sequence: str,
    weights: dict[str, float],
    *,
    exclude_singletons: bool = True,
) -> tuple[float, int, int, float]:
    """CAI, counted codons, excluded codons and the optimal fraction."""

    logs: list[float] = []
    excluded = 0
    optimal = 0
    for start in range(0, len(sequence), 3):
        codon = sequence[start : start + 3]
        weight = weights.get(codon)
        if weight is None:
            raise StepError(
                f"sequence_codon_adaptation: codon '{codon}' is not part of the "
                "standard genetic code"
            )
        if exclude_singletons and codon in _SINGLETON_CODONS:
            excluded += 1
            continue
        logs.append(float(np.log(weight)))
        if weight >= 1.0 - 1e-12:
            optimal += 1
    if not logs:
        raise StepError(
            "sequence_codon_adaptation: the target sequence has no codon left "
            "after excluding ATG/TGG"
        )
    cai = float(np.exp(np.mean(logs)))
    optimal_fraction = optimal / len(logs)
    return cai, len(logs), excluded, optimal_fraction


class SequenceCodonAdaptationStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_codon_adaptation.SequenceCodonAdaptationStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_codon_adaptation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon adaptation index",
        "description": (
            "Codon adaptation index of coding DNA sequences relative to a "
            "reference coding set (Sharp & Li 1987)."
        ),
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                },
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "reference_sequence_dim", "default": "sequence"},
                        {"param": "reference_position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"representation": {"type": "string", "const": "sequence_codes"}},
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if len(inputs) != 2:
            raise StepError(
                "sequence_codon_adaptation: two sequence forms are required "
                "(target, then reference coding set)"
            )
        target, reference = inputs
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        reference_sequence_dim = str(params.get("reference_sequence_dim") or "sequence")
        reference_position_dim = str(params.get("reference_position_dim") or "position")
        out_dim = str(params.get("sequence_output_dim") or "sequence")
        out_name = str(params.get("output") or "cai")
        exclude_singletons = params.get("exclude_singletons")
        exclude_singletons = True if exclude_singletons is None else bool(exclude_singletons)
        absent_weight = params.get("absent_weight")
        absent_weight = _ABSENT_WEIGHT if absent_weight is None else float(absent_weight)

        if not 0.0 < absent_weight <= 1.0:
            raise StepError(
                "sequence_codon_adaptation: absent_weight must be in (0, 1]"
            )

        target_names = _sequence_names(target, sequence_dim)
        reference_names = _sequence_names(reference, reference_sequence_dim)
        targets = _validated(decode_sequences(target, sequence_dim, position_dim), "target")
        references = _validated(
            decode_sequences(reference, reference_sequence_dim, reference_position_dim),
            "reference",
        )
        weights = codon_weights(references, absent_weight)

        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        names: list[str] = []
        for index, sequence in enumerate(targets):
            cai, counted, excluded, optimal = adaptation_index(
                sequence, weights, exclude_singletons=exclude_singletons
            )
            label = target_names[index] if index < len(target_names) else f"seq{index + 1}"
            labels[label] = len(rows)
            names.append(label)
            rows.append([cai, float(counted), float(excluded), optimal])

        out = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[out_dim, "statistic"],
            labels={
                out_dim: labels,
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(targets),
                "n_reference_sequences": len(references),
                "sequence_names": names,
                "reference_names": reference_names,
                "absent_weight": absent_weight,
                "exclude_singletons": exclude_singletons,
                "n_codons_reference": sum(len(sequence) // 3 for sequence in references),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(targets),
            "n_reference_sequences": len(references),
            "absent_weight": absent_weight,
            "exclude_singletons": exclude_singletons,
        }
        print(
            f"[sequence_codon_adaptation] {len(rows)} sequences against "
            f"{len(references)} reference sequences"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
