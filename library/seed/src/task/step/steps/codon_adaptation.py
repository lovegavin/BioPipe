"""Codon adaptation index (CAI) from a CDS set and a reference set."""
from __future__ import annotations

import math

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._annotation_utils import fasta_sequences
from ._codon_bias_utils import AA_CODON_ORDER, CODON_TABLE, STOP_CODONS, clean_cds, codon_counts


def reference_weights(reference_sequences, operator):
    counts = {}
    for raw in reference_sequences:
        sequence = clean_cds(str(raw), operator)
        for codon, value in codon_counts(sequence).items():
            counts[codon] = counts.get(codon, 0) + value
    weights = {}
    optimal = {}
    for aa, codons in AA_CODON_ORDER.items():
        if len(codons) < 2:
            continue
        maximum = max(counts.get(codon, 0) for codon in codons)
        if maximum <= 0:
            continue
        for codon in codons:
            count = counts.get(codon, 0)
            weights[codon] = count / maximum if count else 0.5 / maximum
            if counts.get(codon, 0) == maximum:
                optimal[codon] = aa
    return weights, optimal


def cai_value(sequence, weights, operator):
    sequence = clean_cds(sequence, operator)
    counts = codon_counts(sequence)
    logs = []
    n_used = 0
    for codon, value in counts.items():
        if codon in STOP_CODONS or CODON_TABLE[codon] in "MW":
            continue
        weight = weights.get(codon)
        if weight is None:
            continue
        n_used += value
        if weight <= 0.0:
            return 0.0, n_used
        logs.extend([math.log(weight)] * value)
    if not logs:
        return float("nan"), 0
    return math.exp(sum(logs) / len(logs)), n_used


class CodonAdaptationStep(Step):
    provider = "operon-core"
    parameters_file = "codon_adaptation.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "codon_adaptation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Codon adaptation index",
        "description": "Relative adaptiveness weighted CAI for each CDS against a reference CDS set.",
        "category": "Omics",
        "icon": "Gauge",
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
                },
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
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        size = sum(int(getattr(item, "data", np.empty(0)).nbytes) for item in inputs) if inputs else 0
        return max(2 * size, 16 * 1024 * 1024), 4 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        sequence_dim = params.get("sequence_dim", "sequence")
        position_dim = params.get("position_dim", "position")
        out_name = params.get("output", "codon_adaptation")
        target_names, targets = fasta_sequences(inputs[0], sequence_dim, position_dim, "codon_adaptation")
        _, references = fasta_sequences(inputs[1], sequence_dim, position_dim, "codon_adaptation")
        weights, _ = reference_weights(references, "codon_adaptation")
        if not weights:
            from src.core.errors import StepError

            raise StepError("codon_adaptation: reference set yielded no usable codon weights")
        names, values = [], []
        for name, raw in zip(target_names, targets):
            cai, n_used = cai_value(str(raw), weights, "codon_adaptation")
            names.append(name)
            values.append((cai, n_used))
        data = np.asarray(values, dtype=np.float64)
        out = Form(
            data,
            dims=[sequence_dim, "statistic"],
            labels={sequence_dim: {name: index for index, name in enumerate(names)},
                    "statistic": {"cai": 0, "codons_used": 1}},
            info={"n_sequences": len(names), "reference_sequences": len(references),
                  "mean_cai": float(np.nanmean(data[:, 0])) if len(data) else float("nan")},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_sequences": len(names),
            "mean_cai": float(np.nanmean(data[:, 0])) if len(data) else float("nan"),
        }

    def export(self, ctx):
        return dict(self._export_data)
