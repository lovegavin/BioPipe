"""Hydrophobicity profile of the Kabat CDR loops of a VHH or VH domain."""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from .antibody_cdr_kabat import kabat_regions
from .antibody_developability import longest_run
from .protein_properties import _charge

_STATISTICS = ("length", "hydrophobic_fraction", "max_run", "max_moment", "net_charge_ph7")
_DEFAULT_REGIONS = ("CDR1", "CDR2", "CDR3")
# Kyte-Doolittle hydropathy scale, the classic choice for hydrophobic moments.
_KD = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}
_ANGLE = math.radians(100.0)


def hydrophobic_moment(sequence: str, window: int) -> float:
    """Return the largest Kyte-Doolittle hydrophobic moment over sliding windows."""
    if not sequence:
        return 0.0
    width = max(1, min(int(window), len(sequence)))
    values = [_KD[residue] for residue in sequence]
    best = 0.0
    for start in range(0, len(values) - width + 1):
        real = 0.0
        imaginary = 0.0
        for offset in range(width):
            hydropathy = values[start + offset]
            real += hydropathy * math.cos(offset * _ANGLE)
            imaginary += hydropathy * math.sin(offset * _ANGLE)
        best = max(best, math.hypot(real, imaginary) / width)
    return best


def cdr_hydrophobicity_row(
    sequence: str, *, window: int = 7, ph: float = 7.4, hydrophobic: set[str] | frozenset[str] | None = None
) -> dict[str, float]:
    """Return the hydrophobicity statistics of one CDR loop."""
    residue_set = set(hydrophobic) if hydrophobic is not None else set("AVILMFWY")
    clean = "".join(residue for residue in sequence.upper() if residue in _KD)
    length = len(clean)
    if length == 0:
        return {name: float("nan") for name in _STATISTICS}
    hydrophobic_count = sum(1 for residue in clean if residue in residue_set)
    return {
        "length": float(length),
        "hydrophobic_fraction": hydrophobic_count / length,
        "max_run": float(longest_run(clean, residue_set)),
        "max_moment": hydrophobic_moment(clean, window),
        "net_charge_ph7": float(_charge(clean, ph)),
    }


class AntibodyCdrHydrophobicityStep(Step):
    """Hydrophobicity profile of the Kabat CDR loops of a VHH or VH domain."""

    provider = "operon-core"
    parameters_file = "antibody_cdr_hydrophobicity.AntibodyCdrHydrophobicityStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_cdr_hydrophobicity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Antibody CDR Hydrophobicity",
        "description": (
            "Summarize each Kabat CDR loop of a VHH/VH domain with hydrophobic fraction, "
            "longest hydrophobic run, Kyte-Doolittle hydrophobic moment and net charge."
        ),
        "category": "Machine Learning",
        "icon": "Tag",
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
        "dependencies": ["numpy>=1.24", "biopython>=1.80"],
        "dependency_imports": ["Bio"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        sequence_dim = str(ctx.step_params.get("sequence_dim", "sequence"))
        position_dim = str(ctx.step_params.get("position_dim", "position"))
        region_dim = str(ctx.step_params.get("region_dim", "region"))
        window = int(ctx.step_params.get("window", 7))
        ph = float(ctx.step_params.get("ph", 7.4))
        hydrophobic_text = str(ctx.step_params.get("hydrophobic_residues", "AVILMFWY"))
        requested = [
            item.strip().upper()
            for item in str(ctx.step_params.get("regions", ",".join(_DEFAULT_REGIONS)))
            .replace(";", ",")
            .split(",")
            if item.strip()
        ]
        output_name = str(ctx.step_params.get("output", "cdr_hydrophobicity"))
        if not requested:
            raise StepError("regions must name at least one CDR")
        for name in requested:
            if name not in _DEFAULT_REGIONS:
                raise StepError("regions must be CDR1, CDR2 or CDR3")
        if window < 3 or window > 15:
            raise StepError("window must be between 3 and 15 residues")
        if not 0.0 <= ph <= 14.0:
            raise StepError("ph must be between 0 and 14")
        hydrophobic = set(hydrophobic_text.upper())
        if not hydrophobic:
            raise StepError("hydrophobic_residues must name at least one residue")
        if len(inputs) != 1:
            raise StepError("one sequence form is required")
        form = inputs[0]
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError("the input must have dims [sequence, position]")
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("the sequence form is empty")
        if len(sequences) != 1:
            raise StepError("exactly one sequence is supported so the region labels stay unique")
        regions = {name: sequence for name, _start, _end, sequence in kabat_regions(sequences[0])}
        rows = [
            cdr_hydrophobicity_row(regions[name], window=window, ph=ph, hydrophobic=hydrophobic)
            for name in requested
        ]
        values = np.asarray(
            [[row[name] for name in _STATISTICS] for row in rows], dtype=np.float32
        )
        output = Form(
            data=values,
            dims=[region_dim, "statistic"],
            labels={
                region_dim: {name: index for index, name in enumerate(requested)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "region_sequences": {name: regions[name] for name in requested},
                "regions": list(requested),
                "window": window,
                "ph": ph,
                "hydrophobic_residues": "".join(sorted(hydrophobic)),
                "hydropathy_scale": "kyte-doolittle",
                "moment_angle_degrees": 100.0,
                "numbering_scheme": "kabat",
            },
        )
        output.validate()
        ctx[output_name] = output
        self._export_data = {
            "n_regions": len(requested),
            "regions": list(requested),
            "lengths": {name: len(regions[name]) for name in requested},
            "max_moments": {
                name: round(float(values[index, 3]), 4) for index, name in enumerate(requested)
            },
            "window": window,
        }
        print(
            f"[antibody_cdr_hydrophobicity] {len(requested)} CDR regions, "
            f"max moment {float(values[:, 3].max()):.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
