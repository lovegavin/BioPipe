"""CDR length and composition profile across antibody sequences."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._sequence_common import decode_sequences
from src.task.step.steps.antibody_cdr_kabat import kabat_regions

HYDROPHOBIC = set("AVILMFWY")
STATISTICS = (
    "cdr1_length",
    "cdr2_length",
    "cdr3_length",
    "total_cdr_length",
    "cdr3_hydrophobic_fraction",
    "cdr3_net_charge",
)


def parse_regions(text: str) -> list[str]:
    regions = [item.strip().upper() for item in str(text or "").split(",") if item.strip()]
    if not regions:
        raise StepError("antibody_cdr_length_profile: regions must name at least one CDR")
    allowed = {"CDR1", "CDR2", "CDR3"}
    unknown = [region for region in regions if region not in allowed]
    if unknown:
        raise StepError(
            f"antibody_cdr_length_profile: regions must be CDR1, CDR2 or CDR3, got {unknown}"
        )
    return regions


def cdr_rows(sequence: str) -> dict:
    regions = {name: residues for name, _start, _end, residues in kabat_regions(sequence)}
    cdr = {name: residues for name, residues in regions.items() if name.startswith("CDR")}
    cdr3 = cdr.get("CDR3", "")
    charge = sum(1 for residue in cdr3 if residue in "KR") - sum(1 for residue in cdr3 if residue in "DE")
    return {
        "cdr1_length": float(len(cdr.get("CDR1", ""))),
        "cdr2_length": float(len(cdr.get("CDR2", ""))),
        "cdr3_length": float(len(cdr3)),
        "total_cdr_length": float(sum(len(value) for value in cdr.values())),
        "cdr3_hydrophobic_fraction": (
            float(sum(1 for residue in cdr3 if residue in HYDROPHOBIC) / len(cdr3)) if cdr3 else 0.0
        ),
        "cdr3_net_charge": float(charge),
        "_cdr": dict(cdr),
    }


class AntibodyCdrLengthProfileStep(Step):
    provider = "operon-core"
    parameters_file = "antibody_cdr_length_profile.AntibodyCdrLengthProfileStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "antibody_cdr_length_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CDR length profile",
        "description": "Reports Kabat CDR lengths, hydrophobic fraction and CDR3 net charge per sequence.",
        "category": "Machine Learning",
        "icon": "Tag",
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
                "info": {"representation": {"type": "string", "const": "sequence_codes"}},
            }],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24", "biopython>=1.80"],
        "dependency_imports": ["Bio"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx, inputs) -> None:
        form = inputs[0]
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim") or "sequence")
        position_dim = str(params.get("position_dim") or "position")
        region_dim = str(params.get("region_dim") or "sequence")
        out_name = str(params["output"])

        if len(form.dims) != 2 or list(form.dims) != [sequence_dim, position_dim]:
            raise StepError(
                f"antibody_cdr_length_profile: a sequence form with dims [{sequence_dim}, {position_dim}] "
                f"is required, got {list(form.dims)}"
            )
        sequences = [sequence for sequence in decode_sequences(form, sequence_dim, position_dim) if sequence]
        if not sequences:
            raise StepError("antibody_cdr_length_profile: the form contains no sequences")
        parse_regions(params.get("regions", "CDR1,CDR2,CDR3"))

        rows = [cdr_rows(sequence) for sequence in sequences]
        labels = {f"seq{index + 1}": index for index in range(len(rows))}
        data = np.asarray([[row[name] for name in STATISTICS] for row in rows], dtype=np.float32)
        output = Form(
            data=data,
            dims=[region_dim, "statistic"],
            labels={region_dim: labels, "statistic": {name: index for index, name in enumerate(STATISTICS)}},
            info={
                "missing_code": float("nan"),
                "n_sequences": len(rows),
                "mean_cdr3_length": float(np.mean([row["cdr3_length"] for row in rows])),
                "sequences": [
                    {"name": f"seq{index + 1}", "length": len(sequence), "cdr": row["_cdr"]}
                    for index, (sequence, row) in enumerate(zip(sequences, rows))
                ],
            },
            axis_info={},
        )
        output.validate()
        ctx[out_name] = output
        self._export_data = {
            "n_sequences": len(rows),
            "mean_cdr3_length": output.info["mean_cdr3_length"],
            "max_cdr3_length": int(max(row["cdr3_length"] for row in rows)),
        }
        print(
            f"[antibody_cdr_length_profile] {len(rows)} sequences, mean CDR3 "
            f"{output.info['mean_cdr3_length']:.1f} aa"
        )

    def export(self, ctx) -> dict:
        return getattr(self, "_export_data", {})
