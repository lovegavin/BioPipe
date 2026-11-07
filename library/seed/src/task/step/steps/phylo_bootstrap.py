"""Non-parametric bootstrap support for a neighbour-joining tree."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._phylo_infer import aligned_sequences
from src.task.step.steps._phylo_support_utils import bootstrap


class PhyloBootstrapStep(Step):
    """Resample alignment columns and report split support on the NJ tree."""

    provider = "operon-core"
    parameters_file = "phylo_bootstrap.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "phylo_bootstrap",
        "version": "1.0.0",
        "kind": "operator",
        "title": "phylo_bootstrap",
        "description": "Bootstrap support for a neighbour-joining tree (JC69).",
        "category": "Phylogenetics",
        "icon": "Repeat",
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
        return max(size * 6, 8 * 2 ** 20), 4 * 2 ** 20

    def run(self, ctx, inputs):
        params = ctx.step_params
        sequence_dim = str(params.get("sequence_dim", "sequence"))
        position_dim = str(params.get("position_dim", "position"))
        resamples = int(params.get("resamples", 100))
        seed = int(params.get("seed", 0))
        split_dim = str(params.get("split_dim", "split"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", "bootstrap"))
        records = aligned_sequences(inputs[0], sequence_dim, position_dim, "phylo_bootstrap")
        edges, names, splits, support = bootstrap(records, resamples, seed)
        labels = sorted(support)
        if not labels:
            raise ValueError("phylo_bootstrap: the reference tree has no non-trivial splits")
        data = np.asarray([[support[label]] for label in labels], dtype=np.float64)
        values = list(support.values())
        summary = {
            "n_resamples": resamples,
            "seed": seed,
            "n_splits": len(labels),
            "n_tips": len(names),
            "mean_support": float(np.mean(values)),
            "min_support": float(np.min(values)),
            "max_support": float(np.max(values)),
            "method": "JC69 complete deletion, neighbour joining",
            "splits": {label: support[label] for label in labels},
        }
        out = Form(
            data,
            dims=[split_dim, statistic_dim],
            labels={
                split_dim: {label: index for index, label in enumerate(labels)},
                statistic_dim: {"support": 0},
            },
            info=summary,
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_resamples": resamples,
            "n_splits": len(labels),
            "mean_support": float(np.mean(values)),
        }

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
