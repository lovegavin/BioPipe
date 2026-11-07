"""Graft antibody CDR loops from a donor VH/VHH onto an acceptor framework.

Both sequences are segmented with the conserved-anchor Kabat assignment used by
``antibody_cdr_kabat``; every requested CDR of the acceptor is replaced by the
donor loop, keeping the acceptor framework outside the grafted spans.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.antibody_cdr_kabat import kabat_regions

_STATISTICS = ("acceptor_length", "grafted_length", "length_delta", "n_grafted")
_GRAFTABLE = ("CDR1", "CDR2", "CDR3")


def _regions(sequence: str, role: str) -> dict[str, tuple[int, int, str]]:
    try:
        rows = kabat_regions(sequence)
    except StepError as error:
        message = str(error)
        if message.startswith("antibody_cdr_kabat:"):
            message = "antibody_cdr_graft:" + message.split(":", 1)[1]
        raise StepError(f"{message} ({role} sequence)") from error
    return {name: (start, end, residues) for name, start, end, residues in rows}


def graft_sequence(
    donor: str,
    acceptor: str,
    regions: tuple[str, ...] = _GRAFTABLE,
) -> tuple[str, list[dict]]:
    """Replace the acceptor CDRs by the donor loops; return the graft and metadata."""

    donor_regions = _regions(donor, "donor")
    acceptor_regions = _regions(acceptor, "acceptor")
    replacements: list[tuple[int, int, int, str, str, str]] = []
    for region in regions:
        if region not in _GRAFTABLE:
            raise StepError(
                f"antibody_cdr_graft: region must be one of {list(_GRAFTABLE)}, got '{region}'"
            )
        d_start, d_end, d_residues = donor_regions[region]
        a_start, a_end, a_residues = acceptor_regions[region]
        replacements.append((a_start, a_end, d_start, d_residues, region, a_residues))

    grafted = acceptor
    metadata: list[dict] = []
    for a_start, a_end, d_start, d_residues, region, a_residues in sorted(
        replacements, key=lambda item: item[0], reverse=True
    ):
        grafted = grafted[: a_start - 1] + d_residues + grafted[a_end:]
        metadata.append(
            {
                "region": region,
                "acceptor_start": a_start,
                "acceptor_end": a_end,
                "donor_start": d_start,
                "donor_length": len(d_residues),
                "acceptor_length": len(a_residues),
                "donor_residues": d_residues,
                "acceptor_residues": a_residues,
            }
        )
    metadata.sort(key=lambda item: _GRAFTABLE.index(item["region"]))
    return grafted, metadata


class AntibodyCdrGraftStep(Step):
    provider = "operon-core"
    parameters_file = "antibody_cdr_graft.AntibodyCdrGraftStep.parameters.json"

    definition: dict[str, Any] = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_cdr_graft",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CDR grafting",
        "description": (
            "Graft donor CDR-H1/H2/H3 loops onto an acceptor VH/VHH framework "
            "using conserved-anchor Kabat boundaries."
        ),
        "category": "Machine Learning",
        "icon": "Dna",
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
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "biopython>=1.81"],
        "dependency_imports": ["numpy", "Bio"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("antibody_cdr_graft: a sequence form input is required")
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        graft_dim = str(params.get("graft_dim") or "graft")
        out_name = str(params.get("output") or "grafts")
        donor_index = params.get("donor_index")
        donor_index = 1 if donor_index is None else donor_index
        acceptor_index = params.get("acceptor_index")
        acceptor_index = 2 if acceptor_index is None else acceptor_index
        region_text = str(params.get("regions") or "CDR1,CDR2,CDR3").strip()

        if list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                "antibody_cdr_graft: sequence input expected "
                f"[{sequence_dim}, {position_dim}], got {list(form.dims)}"
            )
        for name, value in (("donor_index", donor_index), ("acceptor_index", acceptor_index)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise StepError(f"antibody_cdr_graft: {name} must be an integer")
        if donor_index == acceptor_index:
            raise StepError("antibody_cdr_graft: donor_index and acceptor_index must differ")

        regions = tuple(
            part.upper()
            for part in region_text.replace(",", " ").split()
            if part
        )
        if not regions:
            raise StepError("antibody_cdr_graft: at least one CDR region is required")
        unknown = [region for region in regions if region not in _GRAFTABLE]
        if unknown:
            raise StepError(
                f"antibody_cdr_graft: unknown regions {unknown}; use a subset of {list(_GRAFTABLE)}"
            )
        if len(set(regions)) != len(regions):
            raise StepError("antibody_cdr_graft: regions must not repeat")

        sequences = decode_sequences(form, sequence_dim, position_dim)
        count = len(sequences)
        for name, value in (("donor_index", donor_index), ("acceptor_index", acceptor_index)):
            if not 1 <= value <= count:
                raise StepError(
                    f"antibody_cdr_graft: {name} {value} is outside the {count} input sequences"
                )
        donor = sequences[donor_index - 1]
        acceptor = sequences[acceptor_index - 1]
        grafted, metadata = graft_sequence(donor, acceptor, regions)

        labels = sorted(form.labels.get(sequence_dim, {}).items(), key=lambda item: item[1])
        acceptor_name = str(labels[acceptor_index - 1][0]) if labels else f"seq{acceptor_index}"

        row = [
            float(len(acceptor)),
            float(len(grafted)),
            float(len(grafted) - len(acceptor)),
            float(len(metadata)),
        ]
        out = Form(
            data=np.asarray([row], dtype=np.float32),
            dims=[graft_dim, "statistic"],
            labels={
                graft_dim: {f"{acceptor_name}_graft": 0},
                "statistic": {name: position for position, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "donor_index": int(donor_index),
                "acceptor_index": int(acceptor_index),
                "regions": list(regions),
                "donor_sequence": donor,
                "acceptor_sequence": acceptor,
                "grafted_sequence": grafted,
                "graft_metadata": metadata,
                "n_grafted": len(metadata),
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "donor_index": int(donor_index),
            "acceptor_index": int(acceptor_index),
            "regions": list(regions),
            "acceptor_length": len(acceptor),
            "grafted_length": len(grafted),
            "n_grafted": len(metadata),
        }
        print(
            f"[antibody_cdr_graft] grafted {', '.join(regions)} "
            f"({len(acceptor)} -> {len(grafted)} aa)"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
