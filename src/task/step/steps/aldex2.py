# src/task/step/steps/aldex2.py
"""Compositional differential abundance (ALDEx-style Monte Carlo CLR test).

This follows the ALDEx2 idea: counts are converted to a probability
vector with a Dirichlet/Gamma Monte Carlo, log-ratio transformed, and a
Welch t-test is applied per taxon. The p-values are averaged over
Monte Carlo instances and BH-corrected.

It is an independent implementation, not a byte-for-byte R ALDEx2
wrapper. The R package's exact Monte Carlo and effect-size conventions
are recorded in the test notes; outputs are labelled explicitly.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._da_common import clr_test, prepare
from ._ext_common import axis_labels, correct, make_form

_COLUMNS = ["logFC", "effect", "P_VALUE", "Q_VALUE", "n_mc", "n_a", "n_b"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")


class Aldex2Step(Step):
    name = "aldex2"
    title = "Compositional differential abundance"
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
            "n_mc": {"type": "integer", "minimum": 8, "default": 128},
            "seed": {"type": "integer", "default": 0},
            "pseudocount": {"type": "number", "exclusiveMinimum": 0, "default": 0.5},
            "monte_carlo": {"type": "boolean", "default": True},
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
        n_mc = int(ctx.step_params.get("n_mc", 128))
        seed = int(ctx.step_params.get("seed", 0))
        pseudocount = float(ctx.step_params.get("pseudocount", 0.5))
        monte_carlo = bool(ctx.step_params.get("monte_carlo", True))
        correction = ctx.step_params.get("correction", "fdr")
        out_name = ctx.step_params.get("output", self.name)
        if n_mc < 8:
            raise StepError("aldex2: n_mc must be >= 8")
        if pseudocount <= 0:
            raise StepError("aldex2: pseudocount must be > 0")
        if correction not in _CORRECTIONS:
            raise StepError(f"aldex2: unknown correction {correction!r}")
        data, a, b, taxa = prepare(table, meta, sample_dim, taxon_dim, group_label, group_a, group_b)
        diff, effect, p, n_a, n_b = clr_test(
            data, a, b, n_mc=n_mc, seed=seed, pseudocount=pseudocount,
            monte_carlo=monte_carlo,
        )
        q = correct(p, correction)
        out = np.column_stack([diff, effect, p, q,
                               np.full(len(taxa), n_mc), np.full(len(taxa), n_a),
                               np.full(len(taxa), n_b)])
        form = make_form(
            out, [taxon_dim, "statistic"],
            {taxon_dim: axis_labels(taxa, taxon_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        self._export_data = {
            "group_a": group_a, "group_b": group_b, "n_a": n_a, "n_b": n_b,
            "n_mc": n_mc, "monte_carlo": monte_carlo, "pseudocount": pseudocount,
            "significant": int((q < 0.05).sum()),
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
