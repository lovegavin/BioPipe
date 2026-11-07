"""Single-gene deletion growth screen on an SBML flux balance model."""
import numpy as np

from src.task.context import Context
from src.task.step.base import Step, Form


from ._fba_utils import gene_growth, parse_sbml, sbml_path, solve

_FIELDS = ["growth_rate", "growth_ratio", "is_essential"]


class FbaGeneKnockoutStep(Step):
    provider = "operon-core"
    parameters_file = "fba_gene_knockout.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "fba_gene_knockout",
        "version": "1.0.0",
        "kind": "operator",
        "title": "FBA gene knockout",
        "description": "Delete each gene in turn and report the resulting growth rate and essentiality.",
        "category": "Metabolism",
        "icon": "Trash2",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "kind": "file",
                    "numeric": False,
                    "ndim": 0,
                    "dims": [],
                    "info": {"representation": {"type": "string", "enum": ["sbml", "xml"]}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 32 * 1024 * 1024, 8 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        model = parse_sbml(sbml_path(inputs[0], "fba_gene_knockout"))
        threshold = float(params.get("growth_threshold", 0.01))
        limit = int(params.get("max_genes", 0))
        reference, _ = solve(model)
        genes = list(model["genes"])
        if limit > 0:
            genes = genes[:limit]
        rows = []
        for gene in genes:
            growth, ratio = gene_growth(model, gene, reference)
            rows.append([growth, ratio, 1.0 if ratio < threshold else 0.0])
        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, 3), dtype=float)
        gene_dim = str(params.get("gene_dim", "gene"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", "knockout"))
        ctx[out_name] = Form(
            data,
            dims=[gene_dim, statistic_dim],
            labels={
                gene_dim: {gene: index for index, gene in enumerate(genes)},
                statistic_dim: {name: index for index, name in enumerate(_FIELDS)},
            },
            info={
                "n_genes": len(genes),
                "n_essential": int(np.sum(data[:, 2])) if len(data) else 0,
                "reference_growth": reference,
                "growth_threshold": threshold,
            },
        )

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "knockout"))]
        return {
            "n_genes": int(form.info["n_genes"]),
            "n_essential": int(form.info["n_essential"]),
            "reference_growth": float(form.info["reference_growth"]),
        }
