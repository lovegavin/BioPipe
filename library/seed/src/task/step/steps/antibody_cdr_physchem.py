"""Physicochemical profile of the Kabat CDR loops of a VH/VHH domain."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from .antibody_cdr_kabat import kabat_regions
from .antibody_developability import _HYDROPHOBIC, count_motif, count_sequons
from .protein_properties import _MW, _charge, _isoelectric

STATISTICS = (
    "length",
    "molecular_weight",
    "isoelectric_point",
    "net_charge_ph7",
    "hydrophobic_fraction",
    "n_glycosylation",
    "n_deamidation",
    "n_cysteines",
)
_DEFAULT_REGIONS = ("CDR1", "CDR2", "CDR3")


def cdr_physchem_row(sequence: str, *, ph: float = 7.4, hydrophobic: set[str] | None = None) -> list[float]:
    """Return the physicochemical statistics of one CDR sequence."""
    residues = hydrophobic or _HYDROPHOBIC
    clean = "".join(amino for amino in sequence.upper() if amino in _MW)
    length = len(clean)
    if not length:
        return [float("nan")] * len(STATISTICS)
    weight = sum(_MW[amino] for amino in clean) - (length - 1) * 18.01524
    hydrophobic_count = sum(1 for amino in clean if amino in residues)
    return [
        float(length),
        float(weight),
        float(_isoelectric(clean)),
        float(_charge(clean, ph)),
        float(hydrophobic_count / length),
        float(count_sequons(clean)),
        float(count_motif(clean, "NG") + count_motif(clean, "NS")),
        float(clean.count("C")),
    ]


class AntibodyCdrPhyschemStep(Step):
    """Per-CDR charge, pI, hydrophobicity and PTM motifs of a VH/VHH domain."""

    provider = 'operon-core'
    parameters_file = 'antibody_cdr_physchem.AntibodyCdrPhyschemStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'antibody_cdr_physchem',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'CDR physicochemical profile',
        'description': (
            'Annotate the Kabat CDR-H1/H2/H3 loops of a VH or VHH sequence and '
            'report length, molecular weight, isoelectric point, net charge at '
            'pH 7.4, hydrophobic fraction and PTM motif counts for each loop.'
        ),
        'category': 'Machine Learning',
        'icon': 'Scales',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1,
                    'numeric': True,
                    'info': {
                        'representation': {'type': 'string', 'const': 'sequence_codes'},
                        'alphabet': {'type': 'string', 'const': 'protein'},
                        'missing_code': {'type': ['number', 'null']},
                    },
                    'dims': [
                        {'param': 'sequence_dim', 'default': 'sequence'},
                        {'param': 'position_dim', 'default': 'position'},
                    ],
                    'labels': [],
                    'parallel': [],
                    'ndim': 2,
                }
            ],
            'output': {
                'mode': 'declare',
                'schema': {
                    'ndim': 2,
                    'numeric': True,
                    'info_open': True,
                    'axis_info_open': True,
                    'info': {'missing_code': {'type': ['number', 'null']}},
                },
            },
        },
        'resources': {
            'memory_modes': ['full'],
            'supports_cuda': False,
            'estimate': 'estimate_memory',
        },
        'dependencies': ['numpy>=1.24', 'biopython>=1.80'],
        'dependency_imports': ['Bio'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")).strip() or "sequence"
        position_dim = str(params.get("position_dim", "position")).strip() or "position"
        region_dim = str(params.get("region_dim", "region")).strip() or "region"
        requested = [
            item.strip().upper()
            for item in str(params.get("regions", ",".join(_DEFAULT_REGIONS))).replace(
                ";", ","
            ).split(",")
            if item.strip()
        ]
        ph = float(params.get("ph", 7.4))
        out_name = params.get("output", self.name)

        if not requested:
            raise StepError("antibody_cdr_physchem: regions must name at least one CDR")
        for name in requested:
            if name not in _DEFAULT_REGIONS:
                raise StepError(
                    "antibody_cdr_physchem: regions must be CDR1, CDR2 or CDR3"
                )
        if not 0.0 <= ph <= 14.0:
            raise StepError("antibody_cdr_physchem: ph must be between 0 and 14")
        if len(inputs) != 1:
            raise StepError("antibody_cdr_physchem: one sequence form is required")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "antibody_cdr_physchem: the input must have dims [sequence, position]"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("antibody_cdr_physchem: the sequence form is empty")
        if len(sequences) != 1:
            raise StepError(
                "antibody_cdr_physchem: exactly one sequence is supported so the region labels stay unique"
            )

        regions = {name: sequence for name, _start, _end, sequence in kabat_regions(sequences[0])}
        rows = [cdr_physchem_row(regions[name], ph=ph) for name in requested]
        data = np.asarray(rows, dtype=np.float32)
        form_out = Form(
            data=data,
            dims=[region_dim, "statistic"],
            labels={
                region_dim: {name: index for index, name in enumerate(requested)},
                "statistic": {name: index for index, name in enumerate(STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "region_sequences": {name: regions[name] for name in requested},
                "regions": list(requested),
                "ph": ph,
                "hydrophobic_residues": "".join(sorted(_HYDROPHOBIC)),
                "numbering_scheme": "kabat",
            },
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_regions": len(requested),
            "regions": list(requested),
            "lengths": {name: len(regions[name]) for name in requested},
            "ph": ph,
        }
        lengths = ", ".join(f"{name}={len(regions[name])}" for name in requested)
        print(f"[{self.name}] {len(requested)} CDR regions ({lengths})")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
