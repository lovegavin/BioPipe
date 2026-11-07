"""Humanization mutations for a VHH framework."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.reader import read_source
from src.task.step.base import Step

from ._sequence_common import PROTEIN_MAP
from .antibody_cdr_kabat import kabat_regions
from .vhh_humanization_score import (
    REFERENCE_FRAMEWORKS,
    _aligner,
    humanization_rows,
)


FRAMEWORKS = ("FR1", "FR2", "FR3", "FR4")
REGION_INDEX = {"FR1": 1, "CDR1": 2, "FR2": 3, "CDR2": 4, "FR3": 5, "CDR3": 6, "FR4": 7}


def humanization_mutations(sequence: str) -> tuple[list[dict], str]:
    """Return framework mismatches and the reference-substituted sequence."""

    cleaned = str(sequence or "").strip().upper()
    if not cleaned:
        raise StepError("vhh_humanization_mutations: the input carries an empty sequence")
    regions = {
        name: (start, end, residues) for name, start, end, residues in kabat_regions(cleaned)
    }
    aligner = _aligner()
    proposed = list(cleaned)
    rows: list[dict] = []
    for name in FRAMEWORKS:
        reference = REFERENCE_FRAMEWORKS.get(name, "")
        if not reference:
            continue
        start, _end, residues = regions.get(name, (0, 0, ""))
        if not residues:
            continue
        alignment = aligner.align(residues, reference)[0]
        for (q_start, q_end), (r_start, r_end) in zip(alignment.aligned[0], alignment.aligned[1]):
            for offset in range(q_end - q_start):
                donor_residue = residues[q_start + offset]
                reference_residue = reference[r_start + offset]
                if donor_residue == reference_residue:
                    continue
                position = start + q_start + offset
                rows.append(
                    {
                        "position": position,
                        "donor": donor_residue,
                        "reference": reference_residue,
                        "region_index": REGION_INDEX[name],
                        "region": name,
                    }
                )
                proposed[position - 1] = reference_residue
    rows.sort(key=lambda row: row["position"])
    return rows, "".join(proposed)


class VhhHumanizationMutationsStep(Step):
    """List the framework substitutions that humanize a VHH."""

    provider = "operon-core"
    parameters_file = (
        "vhh_humanization_mutations.VhhHumanizationMutationsStep.parameters.json"
    )
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "vhh_humanization_mutations",
        "version": "1.0.0",
        "kind": "operator",
        "title": "VHH humanization mutations",
        "description": (
            "Compare the Kabat frameworks of a VHH with the human IGHV3-23/IGHJ4 "
            "reference and return every mismatch together with the "
            "reference-substituted sequence."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "representation": {"type": "string", "const": "sequence_codes"},
                        "alphabet_map": {"type": "object"},
                        "unknown_code": {"type": "integer"},
                    },
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
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence")) or "sequence"
        position_dim = str(params.get("position_dim", "position")) or "position"
        mutation_dim = str(params.get("mutation_dim", "mutation")) or "mutation"
        out_name = str(params.get("output", "mutations")) or "mutations"

        from ._sequence_common import decode_sequences

        sequences = decode_sequences(inputs[0], sequence_dim, position_dim)
        if len(sequences) != 1:
            raise StepError(
                f"vhh_humanization_mutations: expected exactly one sequence, got {len(sequences)}"
            )
        donor = sequences[0]
        rows, proposed = humanization_mutations(donor)
        if not rows:
            raise StepError(
                "vhh_humanization_mutations: the input frameworks already match the "
                "human reference"
            )
        scored = humanization_rows(donor, operator="vhh_humanization_mutations")
        mismatches = scored[-1][1]
        if mismatches != len(rows):
            raise StepError(
                "vhh_humanization_mutations: internal mismatch count "
                f"{len(rows)} disagrees with the framework comparison {mismatches}"
            )

        labels = {
            mutation_dim: {
                f"mut{index + 1}": index for index in range(len(rows))
            },
            "statistic": {
                name: index
                for index, name in enumerate(
                    ("position", "donor_code", "reference_code", "region_index")
                )
            },
        }
        data = np.zeros((len(rows), 4), dtype=np.float32)
        for index, row in enumerate(rows):
            data[index] = (
                row["position"],
                PROTEIN_MAP.get(row["donor"], 20),
                PROTEIN_MAP.get(row["reference"], 20),
                row["region_index"],
            )
        ctx[out_name] = Form(
            data=data,
            dims=[mutation_dim, "statistic"],
            labels=labels,
            info={
                "missing_code": np.nan,
                "n_mutations": len(rows),
                "donor_sequence": donor,
                "proposed_sequence": proposed,
                "regions": [row["region"] for row in rows],
                "reference": "IGHV3-23*01 + IGHJ4*01 (Kabat frameworks)",
            },
        )
        self._export_data = {
            "n_mutations": len(rows),
            "proposed_sequence": proposed,
            "mutations": [f"{row['donor']}{row['position']}{row['reference']}" for row in rows],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
