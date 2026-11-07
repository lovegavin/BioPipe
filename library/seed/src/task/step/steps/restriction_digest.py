"""Restriction digest of linear or circular DNA."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._annotation_utils import fasta_sequences
from src.task.step.steps._restriction_utils import (
    digest, gc_fraction, parse_enzymes,
)


class RestrictionDigestStep(Step):
    """Cut DNA with a panel of restriction enzymes."""

    provider = "operon-core"
    parameters_file = "restriction_digest.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "restriction_digest",
        "version": "1.0.0",
        "kind": "operator",
        "title": "restriction_digest",
        "description": "Restriction fragments for a panel of enzymes.",
        "category": "Sequence",
        "icon": "Scissors",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": False, "ndim": 2,
                 "dims": [{"param": "sequence_dim", "default": "sequence"},
                          {"param": "position_dim", "default": "position"}],
                 "labels": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(size * 2, 4 * 2 ** 20), 2 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        enzymes = parse_enzymes(params.get("enzymes", "EcoRI,BamHI,HindIII"))
        circular = bool(params.get("circular", False))
        fragment_dim = str(params.get("fragment_dim", "fragment"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "fragments"))
        names, sequences = fasta_sequences(inputs[0], sequence_dim, position_dim, "restriction_digest")
        rows = []
        labels = {}
        fields = ["sequence_index", "start", "end", "length", "gc"]
        total_cuts = 0
        for index, (name, raw) in enumerate(zip(names, sequences)):
            sequence = str(raw).upper()
            cuts, fragments = digest(sequence, enzymes, circular)
            total_cuts += len(cuts)
            for number, (start, size) in enumerate(fragments):
                end = start + size
                if circular and end > len(sequence):
                    piece = sequence[start:] + sequence[: end - len(sequence)]
                else:
                    piece = sequence[start:end]
                labels[f"{name}:frag{number}"] = len(rows)
                rows.append([float(index), float(start), float(end), float(size), gc_fraction(piece)])
        if not rows:
            raise ValueError("restriction_digest: no fragments were produced")
        data = np.asarray(rows, dtype=np.float64)
        summary = {
            "enzymes": enzymes,
            "circular": circular,
            "n_sequences": len(names),
            "n_fragments": len(rows),
            "total_cuts": total_cuts,
            "ladder_max": float(data[:, 3].max()),
        }
        out = Form(
            data,
            dims=[fragment_dim, field_dim],
            labels={
                fragment_dim: labels,
                field_dim: {name: index for index, name in enumerate(fields)},
            },
            info=summary,
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_fragments": len(rows),
            "total_cuts": total_cuts,
            "n_sequences": len(names),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
