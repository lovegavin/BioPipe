"""Summary statistics of restriction fragment lengths."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step


class RestrictionFragmentStatsStep(Step):
    """Length distribution of a restriction digest."""

    provider = "operon-core"
    parameters_file = "restriction_fragment_stats.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "restriction_fragment_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "restriction_fragment_stats",
        "description": "Summary statistics of restriction fragment lengths.",
        "category": "Sequence",
        "icon": "BarChart3",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "ndim": 2,
                 "dims": [{"param": "fragment_dim", "default": "fragment"},
                          {"param": "field_dim", "default": "field"}],
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
        return max(size * 2, 2 * 2 ** 20), 1 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        fragment_dim = str(params.get("fragment_dim", "fragment"))
        field_dim = str(params.get("field_dim", "field"))
        length_field = str(params.get("length_field", "length"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", "stats"))
        form = inputs[0]
        if fragment_dim not in form.dims or field_dim not in form.dims:
            raise StepError("restriction_fragment_stats: expected fragment and field dimensions")
        fields = form.labels.get(field_dim) or {}
        if length_field not in fields:
            raise StepError(f"restriction_fragment_stats: column {length_field!r} is missing")
        lengths = np.asarray(form.data[:, int(fields[length_field])], dtype=np.float64)
        if lengths.size == 0:
            raise StepError("restriction_fragment_stats: the fragment table is empty")
        rows = [
            ("n_fragments", float(lengths.size)),
            ("total_length", float(lengths.sum())),
            ("min_length", float(lengths.min())),
            ("mean_length", float(lengths.mean())),
            ("median_length", float(np.median(lengths))),
            ("max_length", float(lengths.max())),
            ("n_ge_1000", float(np.count_nonzero(lengths >= 1000))),
            ("n_ge_5000", float(np.count_nonzero(lengths >= 5000))),
            ("largest_fragment", float(lengths.max())),
        ]
        data = np.asarray([[value] for _, value in rows], dtype=np.float64)
        out = Form(
            data,
            dims=[statistic_dim, "value"],
            labels={
                statistic_dim: {name: index for index, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info={"n_fragments": int(lengths.size), "total_length": float(lengths.sum())},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_fragments": int(lengths.size),
            "total_length": float(lengths.sum()),
            "max_length": float(lengths.max()),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
