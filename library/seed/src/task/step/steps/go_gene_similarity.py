"""Best-match-average semantic similarity between pairs of annotated genes."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._go_utils import alt_map, expanded_counts, information_content, parse_obo, read_gaf, term_similarity


def _column(form, field_dim: str, name: str, operator: str) -> list:
    encoder = form.info.get("encoders", {}).get(field_dim, {}).get(name)
    if encoder is None:
        raise StepError(f"{operator}: column '{name}' is missing")
    index = form.labels[field_dim][name]
    return [encoder.inverse.get(int(value), str(int(value))) for value in form.data[:, index]]


class GoGeneSimilarityStep(Step):
    provider = "operon-core"
    parameters_file = "go_gene_similarity.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "go_gene_similarity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GO gene semantic similarity",
        "description": "Best-match-average Resnik similarity between gene pairs annotated with Gene Ontology terms.",
        "category": "Omics",
        "icon": "Network",
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
        out_name = params.get("output", "go_gene_similarity")
        terms = parse_obo(obo_path)
        alias = alt_map(terms)
        annotations, total = read_gaf(gaf_path, aspect, alias, terms)
        ic = information_content(expanded_counts(annotations, terms), total)
        pairs = [name for name, _ in sorted(inputs[0].labels.get(pair_dim, {}).items(), key=lambda item: item[1])]
        if len(pairs) != inputs[0].data.shape[0]:
            pairs = [str(index) for index in range(inputs[0].data.shape[0])]
        left = _column(inputs[0], field_dim, params.get("gene_a_field", "gene_a"), "go_gene_similarity")
        right = _column(inputs[0], field_dim, params.get("gene_b_field", "gene_b"), "go_gene_similarity")
        rows = []
        for gene_a, gene_b in zip(left, right):
            set_a = annotations.get(gene_a, set())
            set_b = annotations.get(gene_b, set())
            if not set_a or not set_b:
                raise StepError(f"go_gene_similarity: no annotations for {gene_a} or {gene_b}")
            matrix = [[term_similarity(a, b, terms, ic)["resnik"] for b in set_b] for a in set_a]
            best_rows = [max(row) for row in matrix]
            best_cols = [max(matrix[i][j] for i in range(len(matrix))) for j in range(len(set_b))]
            bma = (sum(best_rows) / len(best_rows) + sum(best_cols) / len(best_cols)) / 2.0
            rows.append((bma, max(best_rows), float(len(set_a & set_b))))
        if not rows:
            raise StepError("go_gene_similarity: no gene pairs were provided")
        data = np.asarray(rows, dtype=np.float64)
        out = Form(
            data,
            dims=[pair_dim, "statistic"],
            labels={pair_dim: {name: index for index, name in enumerate(pairs)},
                    "statistic": {"best_match_average": 0, "max_similarity": 1, "shared_terms": 2}},
            info={"n_pairs": len(pairs), "n_genes": total, "aspect": aspect},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {"n_pairs": len(pairs), "mean_best_match_average": float(np.mean(data[:, 0]))}

    def export(self, ctx):
        return dict(self._export_data)
