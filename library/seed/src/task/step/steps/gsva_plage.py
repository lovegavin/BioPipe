"""PLAGE gene-set scores following the GSVA implementation.

PLAGE (Pathway Level Analysis of Gene Expression) scores a gene set by
the first right singular vector of the gene-wise standardized
expression matrix restricted to the set. GSVA's ``plage`` method is:

    Z <- t(scale(t(X)))          # gene-wise z-score across samples
    for each set: svd(Z[set, ])$v[, 1]

This operator reproduces that computation. The singular-vector sign is
not identified by SVD, so scores are normalized to make the
largest-magnitude loading positive; comparisons with R GSVA are
therefore exact up to a per-set sign flip.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form, reorder, require_dims


class GsvaPlageStep(Step):
    provider = 'operon-expression'
    parameters_file = 'gsva_plage.GsvaPlageStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'gsva_plage',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'GSVA PLAGE scores',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'gene_dim', 'default': 'gene'},
                                        {'param': 'gene_set_dim', 'default': 'gene_set'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'PLAGE gene-set scores: first right singular vector of the gene-wise z-scored expression of each set (GSVA plage method).'}

    def run(self, ctx: Context, inputs) -> None:
        expr, sets = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        set_dim = ctx.step_params.get("gene_set_dim", "gene_set")
        min_size = int(ctx.step_params.get("min_size", 1))
        out_name = ctx.step_params.get("output", self.name)
        if min_size < 1:
            raise StepError("gsva_plage: min_size must be at least 1")
        require_dims(expr, feature_dim, sample_dim, label="expression")
        require_dims(sets, gene_dim, set_dim, label="gene sets")
        data = reorder(expr, feature_dim, sample_dim)
        samples = labels_in_order(expr, sample_dim)
        genes = labels_in_order(expr, feature_dim)
        if data.size == 0:
            raise StepError("gsva_plage: expression matrix is empty")
        if not np.isfinite(data).all():
            raise StepError("gsva_plage: expression matrix contains non-finite values")
        n_samples = len(samples)
        if n_samples < 2:
            raise StepError("gsva_plage: need at least two samples")
        means = data.mean(axis=1, keepdims=True)
        scales = data.std(axis=1, ddof=1, keepdims=True)
        zero_variance = [genes[i] for i in range(len(genes)) if not scales[i, 0] > 0.0]
        if zero_variance:
            preview = ", ".join(zero_variance[:5])
            raise StepError(
                "gsva_plage: z-scores are undefined for constant genes: " + preview
            )
        zscores = (data - means) / scales

        set_data = reorder(sets, gene_dim, set_dim)
        set_genes = labels_in_order(sets, gene_dim)
        set_names = labels_in_order(sets, set_dim)
        positions = {gene: index for index, gene in enumerate(set_genes)}
        members: list[list[int]] = []
        kept: list[str] = []
        for column, name in enumerate(set_names):
            indices = [
                index
                for index, gene in enumerate(genes)
                if positions.get(gene) is not None and set_data[positions[gene], column] > 0
            ]
            if len(indices) < min_size:
                continue
            members.append(indices)
            kept.append(name)
        if not kept:
            raise StepError(f"gsva_plage: no gene set has at least {min_size} measured genes")
        scores = np.zeros((len(kept), n_samples), dtype=np.float64)
        sizes: dict[str, int] = {}
        for row, (name, indices) in enumerate(zip(kept, members)):
            block = zscores[indices, :]
            if len(indices) == 1:
                norm = float(np.linalg.norm(block[0]))
                if norm <= 0.0:
                    raise StepError(f"gsva_plage: gene set {name!r} carries no signal")
                vector = block[0] / norm
            else:
                _, _, vh = np.linalg.svd(block, full_matrices=False)
                vector = vh[0]
            anchor = int(np.argmax(np.abs(vector)))
            if vector[anchor] < 0:
                vector = -vector
            scores[row, :] = vector
            sizes[name] = len(indices)
        out = make_form(
            scores.T,
            [sample_dim, set_dim],
            {sample_dim: {name: index for index, name in enumerate(samples)},
             set_dim: {name: index for index, name in enumerate(kept)}},
            {"method": "plage", "n_sets": len(kept)},
        )
        ctx[out_name] = out
        self._export = {
            "method": "plage",
            "n_sets": len(kept),
            "n_samples": n_samples,
            "set_sizes": sizes,
        }
        print(f"[{self.name}] n_sets={len(kept)}, n_samples={n_samples}")

    def export(self, ctx: Context) -> dict:
        return self._export
