"""Flux variability analysis on an SBML flux balance model."""
import numpy as np

from src.task.context import Context
from src.task.step.base import Step, Form


from ._fba_utils import flux_variability, parse_sbml, sbml_path

_FIELDS = ["minimum_flux", "maximum_flux", "span"]


class FbaFluxVariabilityStep(Step):
    provider = "operon-core"
    parameters_file = "fba_flux_variability.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "fba_flux_variability",
        "version": "1.0.0",
        "kind": "operator",
        "title": "FBA flux variability",
        "description": "Report the minimum and maximum flux of every reaction at a fraction of optimal growth.",
        "category": "Metabolism",
        "icon": "GitCompare",
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
        model = parse_sbml(sbml_path(inputs[0], "fba_flux_variability"))
        fraction = float(params.get("fraction_of_maximum", 0.9))
        growth, values = flux_variability(model, fraction)
        names = [reaction["id"] for reaction in model["reactions"]]
        data = np.asarray([[low, high, high - low] for low, high in values], dtype=float)
        reaction_dim = str(params.get("reaction_dim", "reaction"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", "fva"))
        ctx[out_name] = Form(
            data,
            dims=[reaction_dim, statistic_dim],
            labels={
                reaction_dim: {name: index for index, name in enumerate(names)},
                statistic_dim: {name: index for index, name in enumerate(_FIELDS)},
            },
            info={
                "growth_rate": growth,
                "fraction_of_maximum": fraction,
                "n_reactions": len(names),
                "n_blocked": int(np.sum(data[:, 2] <= 1e-9)),
            },
        )

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "fva"))]
        return {
            "growth_rate": float(form.info["growth_rate"]),
            "n_reactions": int(form.info["n_reactions"]),
            "n_blocked": int(form.info["n_blocked"]),
        }
