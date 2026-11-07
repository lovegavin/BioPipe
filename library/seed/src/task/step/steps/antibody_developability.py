"""Developability panel for antibody and nanobody sequences."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from .protein_properties import _MW, _charge, _isoelectric

_HYDROPHOBIC = set("AVILMFWY")

STATISTICS = (
    "length",
    "molecular_weight",
    "isoelectric_point",
    "net_charge_ph6",
    "net_charge_ph7",
    "n_cysteines",
    "n_deamidation",
    "n_isomerization",
    "n_glycosylation",
    "longest_hydrophobic_run",
    "hydrophobic_fraction",
    "charge_asymmetry",
)


def count_motif(sequence: str, motif: str) -> int:
    """Count overlapping occurrences of ``motif`` in ``sequence``."""
    if not motif:
        return 0
    return sum(
        1
        for index in range(len(sequence) - len(motif) + 1)
        if sequence[index:index + len(motif)] == motif
    )


def count_sequons(sequence: str) -> int:
    """Count N-X-S/T sequons with X not proline (N-glycosylation motif)."""
    return sum(
        1
        for index in range(len(sequence) - 2)
        if sequence[index] == "N"
        and sequence[index + 1] != "P"
        and sequence[index + 2] in "ST"
    )


def longest_run(sequence: str, alphabet: set[str]) -> int:
    """Longest consecutive run of residues from ``alphabet``."""
    best = 0
    current = 0
    for residue in sequence:
        if residue in alphabet:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def developability_row(
    sequence: str,
    *,
    low_ph: float = 6.0,
    high_ph: float = 7.4,
    hydrophobic: set[str] | None = None,
) -> list[float]:
    """Return the developability statistics of one cleaned protein sequence."""
    residues = hydrophobic or _HYDROPHOBIC
    clean = "".join(aa for aa in sequence if aa in _MW)
    length = len(clean)
    if not length:
        return [float("nan")] * len(STATISTICS)
    weight = sum(_MW[aa] for aa in clean) - (length - 1) * 18.01524
    positives = sum(1 for aa in clean if aa in "KR")
    negatives = sum(1 for aa in clean if aa in "DE")
    hydrophobic_count = sum(1 for aa in clean if aa in residues)
    return [
        float(length),
        float(weight),
        float(_isoelectric(clean)),
        float(_charge(clean, low_ph)),
        float(_charge(clean, high_ph)),
        float(clean.count("C")),
        float(count_motif(clean, "NG") + count_motif(clean, "NS")),
        float(count_motif(clean, "DP")),
        float(count_sequons(clean)),
        float(longest_run(clean, residues)),
        float(hydrophobic_count / length),
        float((positives - negatives) / length),
    ]


class AntibodyDevelopabilityStep(Step):
    provider = 'operon-core'
    """Whole-sequence developability metrics for antibody domains."""
    parameters_file = (
        'antibody_developability.AntibodyDevelopabilityStep.parameters.json'
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'antibody_developability',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Antibody developability panel',
     'category': 'Machine Learning',
     'icon': 'Scales',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {'representation': {'type': 'string', 'const': 'sequence_codes'},
                                        'alphabet': {'type': 'string', 'const': 'protein'},
                                        'missing_code': {'type': ['number', 'null']}},
                               'dims': [{'param': 'sequence_dim', 'default': 'sequence'},
                                        {'param': 'position_dim', 'default': 'position'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'],
                   'supports_cuda': False,
                   'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24'],
     'dependency_imports': [],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'VHH/antibody developability: pI, charge at low and neutral pH, cysteines, deamidation/isomerization/glycosylation motifs, hydrophobic runs.'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        seq_dim = str(params.get("sequence_dim", "sequence"))
        pos_dim = str(params.get("position_dim", "position"))
        out_name = params.get("output", self.name)
        low_ph = float(params.get("low_ph", 6.0))
        high_ph = float(params.get("high_ph", 7.4))
        hydrophobic_text = str(
            params.get("hydrophobic_residues", "AVILMFWY") or "AVILMFWY"
        ).strip().upper()
        sequences = decode_sequences(form, seq_dim, pos_dim)
        rows = [
            developability_row(
                sequence,
                low_ph=low_ph,
                high_ph=high_ph,
                hydrophobic=set(hydrophobic_text),
            )
            for sequence in sequences
        ]
        data = np.asarray(rows, dtype=np.float32)
        out = Form(
            data=data,
            dims=[seq_dim, "statistic"],
            labels={
                seq_dim: dict(form.labels[seq_dim]),
                "statistic": {
                    name: position for position, name in enumerate(STATISTICS)
                },
            },
            info={
                "missing_code": np.nan,
                "n_sequences": len(sequences),
                "statistics": list(STATISTICS),
                "low_ph": low_ph,
                "high_ph": high_ph,
                "hydrophobic_residues": "".join(sorted(set(hydrophobic_text))),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(sequences),
            "statistics": list(STATISTICS),
            "mean_isoelectric_point": (
                float(np.nanmean(data[:, 2])) if len(rows) else None
            ),
        }
        print(f"[antibody_developability] {len(sequences)} sequences")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
