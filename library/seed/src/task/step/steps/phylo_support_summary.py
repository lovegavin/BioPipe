"""Summary statistics for bootstrap split support."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step


class PhyloSupportSummaryStep(Step):
    """Summarise the distribution of bootstrap support values."""

    provider = "operon-core"
    parameters_file = "phylo_support_summary.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_support_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "phylo_support_summary",
        "description": "Counts and quantiles of bootstrap split support.",
        "category": "Phylogenetics",
        "icon": "BarChart3",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "split_dim", "default": "split"},
                          {"param": "statistic_dim", "default": "statistic"}],
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
        return max(size * 2, 4 * 2 ** 20), 1 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        split_dim = str(params.get("split_dim", "split"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        support_field = str(params.get("support_field", "support"))
        threshold = float(params.get("threshold", 0.5))
        out_name = str(params.get("output", "summary"))
        form = inputs[0]
        if split_dim not in form.dims or statistic_dim not in form.dims:
            raise StepError("phylo_support_summary: expected split and statistic dimensions")
        fields = form.labels.get(statistic_dim) or {}
        if support_field not in fields:
            raise StepError(f"phylo_support_summary: support column {support_field!r} is missing")
        values = np.asarray(form.data[:, int(fields[support_field])], dtype=np.float64)
        if values.size == 0:
            raise StepError("phylo_support_summary: the support table is empty")
        rows = [
            ("n_splits", float(values.size)),
            ("mean_support", float(values.mean())),
            ("median_support", float(np.median(values))),
            ("min_support", float(values.min())),
            ("max_support", float(values.max())),
            ("q25_support", float(np.percentile(values, 25))),
            ("q75_support", float(np.percentile(values, 75))),
            ("n_below_threshold", float(np.count_nonzero(values < threshold))),
            ("fraction_below_threshold", float(np.count_nonzero(values < threshold) / values.size)),
        ]
        data = np.asarray([[value] for _, value in rows], dtype=np.float64)
        out = Form(
            data,
            dims=[statistic_dim, "value"],
            labels={
                statistic_dim: {name: index for index, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info={"threshold": threshold, "n_splits": int(values.size)},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_splits": int(values.size),
            "mean_support": float(values.mean()),
            "n_below_threshold": int(np.count_nonzero(values < threshold)),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
