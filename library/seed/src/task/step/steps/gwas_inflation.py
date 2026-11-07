"""Genomic inflation factor and p-value distribution of a GWAS result table."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._gwas_utils import association_rows, inflation


DEFAULTS = {'variant_dim': 'variant', 'statistic_dim': 'statistic', 'output': 'inflation'}


class GwasInflationStep(Step):
    parameters_file = "gwas_inflation.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "gwas_inflation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GWAS genomic inflation",
        "description": "Compute the genomic control inflation factor and summary of the association p-values.",
        "category": "Statistics",
        "icon": "Gauge",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "name": "association",
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "variant_dim", "default": "variant"},
                        {"param": "statistic_dim", "default": "statistic"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "description": "Association table with p, beta and se columns.",
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False},
    }

    parameters = [
        {"name": "variant_dim", "type": "string", "default": "variant"},
        {"name": "statistic_dim", "type": "string", "default": "statistic"},
        {"name": "output", "type": "string", "default": "inflation"},
    ]

    def run(self, ctx, inputs):
        params = {**DEFAULTS, **dict(ctx.step_params or {})}
        rows = association_rows(
            inputs[0], params["variant_dim"], params["statistic_dim"], "gwas_inflation"
        )
        summary = inflation(rows)
        names = ("n_variants", "lambda", "mean_chi2", "median_p", "min_p")
        data = np.asarray([[float(summary[name])] for name in names], dtype=float)
        labels = {
            "statistic": {name: index for index, name in enumerate(names)},
            "value": {"value": 0},
        }
        ctx[params["output"]] = Form(
            data, dims=["statistic", "value"], labels=labels, info=dict(summary)
        )
        self._export = {"lambda": summary["lambda"], "n_variants": summary["n_variants"]}

    def export(self, ctx):
        return dict(self._export)
