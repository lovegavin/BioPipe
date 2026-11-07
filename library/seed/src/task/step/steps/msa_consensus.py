"""Consensus sequence from an alignment, with gap and majority thresholds."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._msa_utils import (
    alignment_records,
    column_statistics,
    consensus_sequence,
    resolve_alphabet,
)
from ._sequence_common import encode_sequences


class MsaConsensusStep(Step):
    provider = "operon-core"
    parameters_file = "msa_consensus.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "msa_consensus",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Alignment consensus sequence",
        "description": (
            "Build a consensus sequence from an alignment, emitting the "
            "majority residue per column unless the column is too gappy or "
            "the majority is too weak (then N for nucleotides, X for protein)."
        ),
        "category": "Sequence",
        "icon": "FileText",
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
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = int(getattr(inputs[0], "data", np.empty(0)).nbytes) if inputs else 0
        return max(size, 8 * 2**20), size

    def run(self, ctx: Context, inputs) -> None:
        if not inputs:
            raise StepError("msa_consensus: an alignment input is required")
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        max_gap_fraction = float(params.get("max_gap_fraction", 0.5))
        min_major_fraction = float(params.get("min_major_fraction", 0.5))
        out_name = str(params.get("output", self.name))
        if not 0.0 <= max_gap_fraction <= 1.0:
            raise StepError("msa_consensus: max_gap_fraction must be within [0, 1]")
        if not 0.0 <= min_major_fraction <= 1.0:
            raise StepError("msa_consensus: min_major_fraction must be within [0, 1]")

        names, sequences = alignment_records(
            inputs[0], sequence_dim, position_dim, "msa_consensus"
        )
        alphabet = resolve_alphabet(sequences, params.get("alphabet", "auto"))
        stats = column_statistics(sequences, alphabet)
        consensus = consensus_sequence(
            stats, alphabet, max_gap_fraction, min_major_fraction
        )
        n_ambiguous = sum(
            1
            for character in consensus
            if character in ("N", "X")
        )
        form = encode_sequences(
            [consensus],
            sequence_dim,
            position_dim,
            alphabet,
            labels={
                sequence_dim: {"consensus": 0},
                position_dim: {str(index): index for index in range(len(consensus))},
            },
            info_extra={
                "source": "msa_consensus",
                "n_sequences": len(sequences),
                "max_gap_fraction": max_gap_fraction,
                "min_major_fraction": min_major_fraction,
                "n_ambiguous": n_ambiguous,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "length": len(consensus),
            "alphabet": alphabet,
            "n_ambiguous": n_ambiguous,
            "max_gap_fraction": max_gap_fraction,
            "min_major_fraction": min_major_fraction,
            "consensus": consensus,
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
