"""Restriction-site scan for DNA sequences."""

from __future__ import annotations

import re

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences

# Common type II restriction enzymes with palindromic recognition sites.
ENZYMES = {
    "EcoRI": "GAATTC",
    "BamHI": "GGATCC",
    "HindIII": "AAGCTT",
    "NotI": "GCGGCCGC",
    "XhoI": "CTCGAG",
    "SalI": "GTCGAC",
    "PstI": "CTGCAG",
    "KpnI": "GGTACC",
    "SacI": "GAGCTC",
    "SmaI": "CCCGGG",
    "NcoI": "CCATGG",
    "XbaI": "TCTAGA",
    "SpeI": "ACTAGT",
    "NdeI": "CATATG",
}

STATISTICS = ("n_sites", "n_enzymes", "first_position")


def site_hits(sequence: str, enzymes: dict[str, str] | None = None) -> dict[str, list[int]]:
    sequence = sequence.upper()
    hits: dict[str, list[int]] = {}
    for name, motif in (enzymes or ENZYMES).items():
        positions = [match.start() + 1 for match in re.finditer(f"(?=({motif}))", sequence)]
        if positions:
            hits[name] = positions
    return hits


def site_row(sequence: str) -> dict:
    hits = site_hits(sequence)
    positions = [position for values in hits.values() for position in values]
    return {
        "n_sites": len(positions),
        "n_enzymes": len(hits),
        "first_position": min(positions) if positions else 0,
        "_hits": hits,
    }


class SequenceRestrictionSitesStep(Step):
    provider = "operon-core"
    parameters_file = "sequence_restriction_sites.SequenceRestrictionSitesStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sequence_restriction_sites",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Restriction site scan",
        "description": "Scans DNA sequences for common type II restriction sites and reports positions.",
        "category": "Omics",
        "icon": "Scissors",
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "sequence_dim", "default": "sequence"},
                    {"param": "position_dim", "default": "position"},
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2,
                "info": {
                    "representation": {"type": "string", "const": "sequence_codes"},
                },
            }],
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
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"sequence_restriction_sites: a sequence form with dims [{sequence_dim}, {position_dim}] "
                f"is required, got {list(form.dims)}"
            )
        sequences = decode_sequences(form, sequence_dim, position_dim)
        if not sequences:
            raise StepError("sequence_restriction_sites: the form contains no sequences")

        rows = []
        names = []
        for index, sequence in enumerate(sequences):
            if not sequence:
                raise StepError(
                    f"sequence_restriction_sites: sequence {index} is empty; the form must stay rectangular"
                )
            cleaned = sequence.upper().replace("U", "T")
            if set(cleaned) - set("ACGTN"):
                raise StepError(
                    f"sequence_restriction_sites: sequence {index} contains non-nucleotide residues"
                )
            rows.append(site_row(cleaned))
            names.append(f"seq{index + 1}")

        labels = {name: index for index, name in enumerate(names)}
        data = np.asarray([[row[name] for name in STATISTICS] for row in rows], dtype=np.float32)
        output = Form(
            data=data,
            dims=[sequence_dim, "statistic"],
            labels={sequence_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "enzymes": dict(ENZYMES),
                "sequences": [
                    {"name": names[index], "length": len(sequences[index]), "hits": row["_hits"]}
                    for index, row in enumerate(rows)
                ],
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_sequences": len(rows),
            "n_sites": int(sum(row["n_sites"] for row in rows)),
            "enzymes": list(ENZYMES),
        }
        print(
            f"[sequence_restriction_sites] {len(rows)} sequences, "
            f"{self._export_data['n_sites']} sites across {len(ENZYMES)} enzymes"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
