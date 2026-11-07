"""Semantic similarity between pairs of Gene Ontology terms."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._go_utils import alt_map, expanded_counts, information_content, parse_obo, read_gaf, term_similarity


def _column(form, field_dim: str, name: str) -> list:
    encoder = form.info.get("encoders", {}).get(field_dim, {}).get(name)
    if encoder is None:
        raise StepError(f"go_term_similarity: column '{name}' is missing")
    index = form.labels[field_dim][name]
    return [encoder.inverse.get(int(value), str(int(value))) for value in form.data[:, index]]


class GoTermSimilarityStep(Step):
    provider = "operon-core"
    parameters_file = "go_term_similarity.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "go_term_similarity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GO term semantic similarity",
        "description": "Resnik, Lin and ancestor Jaccard similarity for GO term pairs using corpus information content.",
        "category": "Omics",
        "icon": "GitCompare",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "pair_dim", "default": "pair"},
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
        pair_dim = params.get("pair_dim", "pair")
        field_dim = params.get("field_dim", "field")
        obo_path = params.get("obo_path", "")
        gaf_path = params.get("gaf_path", "")
        aspect = params.get("aspect", "P")
        out_name = params.get("output", "go_term_similarity")
        terms = parse_obo(obo_path)
        alias = alt_map(terms)
        annotations, total = read_gaf(gaf_path, aspect, alias, terms)
        ic = information_content(expanded_counts(annotations, terms), total)
        pairs = [name for name, _ in sorted(inputs[0].labels.get(pair_dim, {}).items(), key=lambda item: item[1])]
        if len(pairs) != inputs[0].data.shape[0]:
            pairs = [str(index) for index in range(inputs[0].data.shape[0])]
        left = _column(inputs[0], field_dim, params.get("term_a_field", "term_a"))
        right = _column(inputs[0], field_dim, params.get("term_b_field", "term_b"))
        rows = []
        for term_a, term_b in zip(left, right):
            term_a = alias.get(term_a, term_a)
            term_b = alias.get(term_b, term_b)
            if term_a not in terms or term_b not in terms:
                raise StepError(f"go_term_similarity: unknown term {term_a} or {term_b}")
            result = term_similarity(term_a, term_b, terms, ic)
            rows.append((result["resnik"], result["lin"], result["jaccard"], result["ic_a"], result["ic_b"]))
        if not rows:
            raise StepError("go_term_similarity: no term pairs were provided")
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data,
            dims=[pair_dim, "statistic"],
            labels={pair_dim: {name: index for index, name in enumerate(pairs)},
                    "statistic": {"resnik": 0, "lin": 1, "jaccard": 2, "ic_a": 3, "ic_b": 4}},
            info={"n_pairs": len(pairs), "n_genes": total, "aspect": aspect},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_pairs": len(pairs), "mean_lin": float(np.mean(data[:, 1])),
                             "max_resnik": float(data[:, 0].max())}

    def export(self, ctx):
        return dict(self._export_data)
