# src/task/step/steps/gene_list_to_hits.py
"""Build a hits matrix from a gene list and a universe matrix.

Input:
    universe : 2D Form [gene, term]. Only the labels on the gene
               axis are used.
    params   : ``genes`` = list of gene labels

Output:
    hits     : 2D Form [gene, term], containing only the rows of
               the universe whose gene is in ``genes``. Values are
               taken from ``universe > 0``.

The output is a valid hits Form for ``enrich_go``: gene axis is a
subset of the universe, term axis matches the universe. Sending the
full universe with zeroed-out non-hit rows would make
``enrich_go`` count every universe gene as a hit gene (it uses the
hits form's row count as ``n``), so the operator drops non-hit rows
instead.

Params:
    genes    : list of gene labels (required)
    gene_dim : gene axis (default "gene")
    term_dim : term axis (default "go_term")
    output   : context key (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class GeneListToHitsStep(Step):
    """Turn a gene list into a subset hits matrix over a universe."""

    name = "gene_list_to_hits"
    category = "analysis"
    icon = "Intersect"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "genes": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "gene_dim": {"type": "string", "default": "gene"},
            "term_dim": {"type": "string", "default": "go_term"},
            "output": {"type": "string"},
        },
        "required": ["genes"],
        "additionalProperties": False,
    }
    input_contracts = [port(
        ndim=2,
        dims=[param("gene_dim", "gene"), param("term_dim", "go_term")],
    )]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True,
        "info_open": True, "axis_info_open": True,
    }}

    def run(self, ctx: Context, inputs) -> None:
        universe = inputs[0]
        genes = ctx.step_params["genes"]
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        term_dim = ctx.step_params.get("term_dim", "go_term")
        out_name = ctx.step_params.get("output", self.name)

        if universe.data.ndim != 2:
            raise StepError(
                f"gene_list_to_hits: universe must be 2D, "
                f"got ndim={universe.data.ndim}"
            )
        if gene_dim not in universe.dims:
            raise StepError(
                f"gene_list_to_hits: gene_dim '{gene_dim}' not in "
                f"{universe.dims}"
            )
        if term_dim not in universe.dims:
            raise StepError(
                f"gene_list_to_hits: term_dim '{term_dim}' not in "
                f"{universe.dims}"
            )
        if not isinstance(genes, list) or not genes:
            raise StepError(
                "gene_list_to_hits: 'genes' must be a non-empty list"
            )

        gene_labels = universe.labels[gene_dim]
        missing = [g for g in genes if g not in gene_labels]
        if missing:
            raise StepError(
                f"gene_list_to_hits: {len(missing)} gene(s) not in "
                f"universe: {missing[:5]}"
            )

        positions = sorted(gene_labels[g] for g in genes)
        hits = universe.subset_axis(gene_dim, positions)

        binary = (hits.data > 0).astype(np.float32)
        new_info = dict(hits.info)
        new_info["missing_code"] = np.nan
        new_hits = Form(
            data=binary,
            dims=list(hits.dims),
            labels={d: dict(v) for d, v in hits.labels.items()},
            info=new_info,
        )
        ctx[out_name] = new_hits

        n_hit_genes = int(new_hits.data.shape[
            new_hits.dims.index(gene_dim)
        ])
        n_hit_pairs = int(new_hits.data.sum())
        self._export_data = {
            "n_universe_genes": int(universe.data.shape[
                universe.dims.index(gene_dim)
            ]),
            "n_hit_genes": n_hit_genes,
            "n_hit_pairs": n_hit_pairs,
        }
        print(
            f"[gene_list_to_hits] {n_hit_genes} hit genes, "
            f"{n_hit_pairs} (gene, term) pairs"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
