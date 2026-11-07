"""Information content profile for Gene Ontology terms."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._go_utils import alt_map, ancestors, depth, expanded_counts, information_content, parse_obo, read_gaf


def field_values(form, field_dim: str, field_name: str):
    values = form.info.get("encoders", {}).get(field_dim, {}).get(field_name)
    if values is None:
        raise StepError(f"go_ic_profile: column '{field_name}' is missing")
    inverse = values.inverse
    data = form.data
    return [inverse.get(int(value), str(int(value))) for value in data[:, 0]]


class GoIcProfileStep(Step):
    provider = "operon-core"
    parameters_file = "go_ic_profile.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "go_ic_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GO information content profile",
        "description": "Information content, annotated gene count and depth for GO terms in an annotation corpus.",
        "category": "Omics",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "row_dim", "default": "term"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return 512 * 1024 * 1024, 32 * 1024 * 1024

    def run(self, ctx: Context, inputs):
        params = ctx.step_params
        row_dim = params.get("row_dim", "term")
        field_dim = params.get("field_dim", "field")
        term_field = params.get("term_field", "term")
        obo_path = params.get("obo_path", "")
        gaf_path = params.get("gaf_path", "")
        aspect = params.get("aspect", "P")
        out_name = params.get("output", "go_ic_profile")
        terms = parse_obo(obo_path)
        alias = alt_map(terms)
        annotations, total = read_gaf(gaf_path, aspect, alias, terms)
        counts = expanded_counts(annotations, terms)
        ic = information_content(counts, total)
        term_ids = [alias.get(value, value) for value in field_values(inputs[0], field_dim, term_field)]
        rows = []
        for term_id in term_ids:
            rows.append((ic.get(term_id, 0.0), float(counts.get(term_id, 0)), float(depth(term_id, terms)), float(len(terms.get(term_id, {}).get("parents", set())))))
        if not rows:
            raise StepError("go_ic_profile: no terms were provided")
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data,
            dims=[row_dim, "statistic"],
            labels={row_dim: {term: index for index, term in enumerate(term_ids)},
                    "statistic": {"information_content": 0, "annotated_genes": 1, "depth": 2, "n_parents": 3}},
            info={"n_terms": len(term_ids), "n_genes": total, "aspect": aspect},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_terms": len(term_ids), "n_genes": total, "aspect": aspect,
                             "max_information_content": float(data[:, 0].max())}

    def export(self, ctx):
        return dict(self._export_data)
