"""Flux balance analysis: optimal flux distribution of an SBML model."""
import os

import numpy as np

from src.task.context import Context
from src.task.step.base import Step, Form


from ._fba_utils import parse_sbml, sbml_path, solve

_FIELDS = ["flux", "fraction_of_maximum", "is_active"]


class FbaFluxDistributionStep(Step):
    provider = "operon-core"
    parameters_file = "fba_flux_distribution.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'file_artifact',
                     'representations': ['file_artifact'],
                     'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "fba_flux_distribution",
        "version": "1.0.0",
        "kind": "operator",
        "title": "FBA flux distribution",
        "description": "Solve a flux balance model and report the optimal flux of every reaction.",
        "category": "Metabolism",
        "icon": "Activity",
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
        size = 0
        for item in inputs or []:
            for path in getattr(item, "files", {}).values():
                try:
                    size += os.path.getsize(path)
                except OSError:
                    continue
        return max(size * 8, 16 * 1024 * 1024), 8 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        model = parse_sbml(sbml_path(inputs[0], "fba_flux_distribution"))
        growth, fluxes = solve(model)
        names = [reaction["id"] for reaction in model["reactions"]]
        scale = growth if growth > 0 else 1.0
        data = np.asarray(
            [[float(value), float(value) / scale, 1.0 if abs(value) > 1e-9 else 0.0] for value in fluxes],
            dtype=float,
        )
        reaction_dim = str(params.get("reaction_dim", "reaction"))
        statistic_dim = str(params.get("statistic_dim", "statistic"))
        out_name = str(params.get("output", "flux"))
        ctx[out_name] = Form(
            data,
            dims=[reaction_dim, statistic_dim],
            labels={
                reaction_dim: {name: index for index, name in enumerate(names)},
                statistic_dim: {name: index for index, name in enumerate(_FIELDS)},
            },
            info={
                "growth_rate": growth,
                "objective": model["objective"],
                "n_reactions": len(names),
                "n_active": int(np.sum(np.abs(fluxes) > 1e-9)),
            },
        )

    def export(self, ctx):
        form = ctx[str(ctx.step_params.get("output", "flux"))]
        return {
            "growth_rate": float(form.info["growth_rate"]),
            "n_reactions": int(form.info["n_reactions"]),
            "n_active": int(form.info["n_active"]),
        }
