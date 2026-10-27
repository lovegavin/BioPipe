# src/task/step/steps/ancom_bc.py
"""Log-ratio differential abundance with sample-bias removal.

This implements the core contrast used by ANCOM-BC-style analyses:
log-counts are centred per sample (removing sample-specific bias),
the group contrast is estimated, and a Welch test plus BH correction
is reported. It is an independent Python implementation, not a direct
R ANCOMBC wrapper; structural-zero estimation and the full ANCOM-BC
mixed model are intentionally not claimed.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._da_common import ancom_style, prepare
from ._ext_common import axis_labels, correct, make_form

_COLUMNS = ["logFC", "effect", "P_VALUE", "Q_VALUE", "n_a", "n_b"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")


class AncomBcStep(Step):
    name = "ancom_bc"
    title = "Log-ratio differential abundance"
    category = "Microbiome"
    builtin_package = "biopipe-microbiome"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("taxon_dim", "taxon")]),
        {**port(ndim=2, dims=[param("sample_dim", "sample")]), "labels_any": [param("group_label")]},
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "taxon_dim": {"type": "string", "default": "taxon"},
            "group_label": {"type": "string"},
            "group_a": {"type": ["string", "number"]},
            "group_b": {"type": ["string", "number"]},
            "pseudocount": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
            "correction": {"type": "string", "enum": list(_CORRECTIONS), "default": "fdr"},
            "output": {"type": "string"},
        },
        "required": ["group_label", "group_a", "group_b"],
    }

    def run(self, ctx: Context, inputs) -> None:
        table, meta = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        group_label = ctx.step_params["group_label"]
        group_a = ctx.step_params["group_a"]
        group_b = ctx.step_params["group_b"]
        pseudocount = float(ctx.step_params.get("pseudocount", 1.0))
        correction = ctx.step_params.get("correction", "fdr")
        out_name = ctx.step_params.get("output", self.name)
        if pseudocount <= 0:
            raise StepError("ancom_bc: pseudocount must be > 0")
        if correction not in _CORRECTIONS:
            raise StepError(f"ancom_bc: unknown correction {correction!r}")
        data, a, b, taxa = prepare(table, meta, sample_dim, taxon_dim, group_label, group_a, group_b)
        diff, effect, p, n_a, n_b = ancom_style(data, a, b, pseudocount=pseudocount)
        q = correct(p, correction)
        out = np.column_stack([diff, effect, p, q,
                               np.full(len(taxa), n_a), np.full(len(taxa), n_b)])
        form = make_form(
            out, [taxon_dim, "statistic"],
            {taxon_dim: axis_labels(taxa, taxon_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        self._export_data = {
            "group_a": group_a, "group_b": group_b, "n_a": n_a, "n_b": n_b,
            "pseudocount": pseudocount, "significant": int((q < 0.05).sum()),
            "results": [
                {"taxon": taxa[i], "logFC": float(diff[i]), "effect": float(effect[i]),
                 "P_VALUE": float(p[i]), "Q_VALUE": float(q[i])}
                for i in range(len(taxa))
            ],
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_a": n_a, "n_b": n_b, "significant": int((q < 0.05).sum()),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
