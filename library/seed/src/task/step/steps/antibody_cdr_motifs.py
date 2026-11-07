"""Scan Kabat CDR regions of a VH/VHH domain for post-translational liabilities."""

from __future__ import annotations

import re

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.step.base import Step

from ._sequence_common import decode_sequences
from .antibody_cdr_kabat import kabat_regions

_STATISTICS = (
    "length",
    "n_glycosylation",
    "n_deamidation",
    "n_isomerization",
    "n_oxidation",
    "n_cysteines",
    "n_liabilities",
)

# Motifs that are commonly treated as chemical liabilities in developability
# reports. Each entry is (motif, compiled lookahead pattern, liability flag).
_MOTIFS = (
    ("glycosylation", re.compile(r"(?=(N[^P][ST]))"), True),
    ("deamidation", re.compile(r"(?=(NG|NS))"), True),
    ("isomerization", re.compile(r"(?=(DP|DG))"), True),
    ("oxidation", re.compile(r"(?=(M|W))"), False),
    ("cysteine", re.compile(r"(?=(C))"), False),
)

_CDR_NAMES = ("CDR1", "CDR2", "CDR3")


def motif_hits(sequence: str, start: int, end: int) -> dict[str, list[int]]:
    """Return 1-based absolute positions of every motif inside ``[start, end]``."""
    hits: dict[str, list[int]] = {}
    for name, pattern, _ in _MOTIFS:
        positions = [
            match.start() + 1
            for match in pattern.finditer(sequence)
            if start <= match.start() + 1 <= end
        ]
        hits[name] = positions
    return hits


def liability_row(residues: str, hits: dict[str, list[int]]) -> dict[str, float]:
    """Summarize the motif hits for one CDR region."""
    liabilities = (
        hits["glycosylation"] + hits["deamidation"] + hits["isomerization"]
    )
    return {
        "length": float(len(residues)),
        "n_glycosylation": float(len(hits["glycosylation"])),
        "n_deamidation": float(len(hits["deamidation"])),
        "n_isomerization": float(len(hits["isomerization"])),
        "n_oxidation": float(len(hits["oxidation"])),
        "n_cysteines": float(len(hits["cysteine"])),
        "n_liabilities": float(len(liabilities)),
    }


def parse_regions(text: str) -> list[str]:
    """Parse and validate the requested CDR region list."""
    names = [item.strip().upper() for item in str(text).split(",") if item.strip()]
    if not names:
        raise StepError("antibody_cdr_motifs: regions must name at least one CDR")
    unknown = [name for name in names if name not in _CDR_NAMES]
    if unknown:
        raise StepError(
            "antibody_cdr_motifs: regions must be CDR1, CDR2 or CDR3, got "
            + ", ".join(unknown)
        )
    return names


class AntibodyCdrMotifsStep(Step):
    """Scan CDR regions for N-glycosylation, deamidation and oxidation motifs."""

    provider = "operon-core"
    parameters_file = "antibody_cdr_motifs.AntibodyCdrMotifsStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_cdr_motifs",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Antibody CDR Liability Motifs",
        "description": (
            "Scan the Kabat CDR regions of a VH/VHH sequence for N-glycosylation, "
            "deamidation, isomerization, oxidation and free-cysteine motifs and report the "
            "positions and per-region counts."
        ),
        "category": "Machine Learning",
        "icon": "Tag",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "name": "sequence",
                    "dims": [
                        {"param": "sequence_dim", "default": "sequence"},
                        {"param": "position_dim", "default": "position"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet": {"type": "string", "const": "protein"},
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
        if len(inputs) != 1:
            raise StepError("antibody_cdr_motifs: exactly one sequence form is required")
        form = inputs[0]
        sequence_dim = str(ctx.step_params.get("sequence_dim", "sequence"))
        position_dim = str(ctx.step_params.get("position_dim", "position"))
        region_dim = str(ctx.step_params.get("region_dim", "region"))
        regions = parse_regions(ctx.step_params.get("regions", "CDR1,CDR2,CDR3"))
        output_name = str(ctx.step_params.get("output", "liabilities"))
        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "antibody_cdr_motifs: the input must have dims "
                f"[{sequence_dim}, {position_dim}], got {list(form.dims)}"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if len(sequences) != 1:
            raise StepError(
                "antibody_cdr_motifs: exactly one sequence is supported so the region "
                f"labels stay unique, got {len(sequences)}"
            )
        sequence = sequences[0]
        domains = kabat_regions(sequence)
        by_name = {name: (start, end, residues) for name, start, end, residues in domains}
        rows = []
        labels = []
        region_sequences: dict[str, str] = {}
        motif_positions: dict[str, dict[str, list[int]]] = {}
        for name in regions:
            start, end, residues = by_name[name]
            hits = motif_hits(sequence, start, end)
            rows.append([liability_row(residues, hits)[key] for key in _STATISTICS])
            labels.append(name)
            region_sequences[name] = residues
            motif_positions[name] = {key: list(value) for key, value in hits.items()}
        values = np.array(rows, dtype=np.float32)
        output = Form(
            data=values,
            dims=[region_dim, "statistic"],
            labels={
                region_dim: {name: index for index, name in enumerate(labels)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "region_sequences": region_sequences,
                "motif_positions": motif_positions,
                "motifs": {
                    "glycosylation": "N-X-S/T with X not P (liability)",
                    "deamidation": "NG or NS (liability)",
                    "isomerization": "DP or DG (liability)",
                    "oxidation": "M or W (exposure dependent)",
                    "cysteine": "free cysteine candidate",
                },
                "numbering_scheme": "kabat",
                "regions": labels,
                "n_regions": len(labels),
            },
        )
        output.validate()
        ctx[output_name] = output
        total_liabilities = int(values[:, _STATISTICS.index("n_liabilities")].sum())
        self._export_data = {
            "regions": labels,
            "n_liabilities": total_liabilities,
            "region_sequences": region_sequences,
            "motif_positions": motif_positions,
        }
        print(
            f"[antibody_cdr_motifs] {len(labels)} regions, "
            f"{total_liabilities} liabilities"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
