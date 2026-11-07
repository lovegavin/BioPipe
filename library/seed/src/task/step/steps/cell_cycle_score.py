"""Cell-cycle S/G2M scores and phase assignment (Scanpy score_genes)."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form, reorder, require_dims


class CellCycleScoreStep(Step):
    provider = 'operon-core'
    parameters_file = 'cell_cycle_score.CellCycleScoreStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cell_cycle_score',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Cell cycle score',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'cell_dim', 'default': 'cell'},
                                        {'param': 'gene_dim', 'default': 'gene'}],
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
                                         'axis_info_open': False}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['anndata>=0.10', 'scanpy>=1.10'],
     'dependency_imports': ['anndata', 'scanpy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Cell cycle score：接收 2 个输入，输出 Form；主要参数：Cell Dim、Gene Dim、Gene Set Dim、Ctrl Size、N '
                    'Bins、随机种子。'}

    def run(self, ctx: Context, inputs) -> None:
        expr, sets = inputs
        cell_dim = ctx.step_params.get("cell_dim", "cell")
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        set_dim = ctx.step_params.get("gene_set_dim", "gene_set")
        ctrl_size = int(ctx.step_params.get("ctrl_size", 50))
        n_bins = int(ctx.step_params.get("n_bins", 25))
        seed = int(ctx.step_params.get("random_state", 0))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(expr, cell_dim, gene_dim, label="expression")
        require_dims(sets, gene_dim, set_dim, label="gene sets")
        try:
            import anndata as ad
            import scanpy as sc
        except ImportError as exc:
            raise StepError("cell_cycle_score requires anndata and scanpy") from exc
        data = reorder(expr, cell_dim, gene_dim).astype(np.float32)
        cells = labels_in_order(expr, cell_dim)
        genes = labels_in_order(expr, gene_dim)
        adata = ad.AnnData(X=data)
        adata.obs_names = cells
        adata.var_names = genes
        set_data = reorder(sets, gene_dim, set_dim)
        set_genes = labels_in_order(sets, gene_dim)
        set_names = labels_in_order(sets, set_dim)
        if len(set_names) < 2:
            raise StepError("cell_cycle_score needs at least two gene sets (S, G2M)")
        pos = {g: i for i, g in enumerate(set_genes)}
        scores = []
        for name in set_names[:2]:
            members = [g for g in genes if pos.get(g) is not None and set_data[pos[g], set_names.index(name)] > 0]
            if not members:
                raise StepError(f"cell_cycle_score: gene set {name!r} has no measured genes")
            col = f"__cc_{len(scores)}"
            sc.tl.score_genes(adata, members, ctrl_size=ctrl_size, n_bins=n_bins,
                              random_state=seed, score_name=col)
            scores.append(np.asarray(adata.obs[col], dtype=np.float64))
        phase = np.where(scores[0] >= scores[1], 0.0, 1.0)
        data_out = np.column_stack([scores[0], scores[1], phase]).astype(np.float32)
        out = make_form(data_out, [cell_dim, "statistic"],
                        {cell_dim: {name: i for i, name in enumerate(cells)},
                         "statistic": {"S_score": 0, "G2M_score": 1, "phase_code": 2}},
                        info={"phase_names": {0: "S", 1: "G2M"}})
        ctx[out_name] = out
        self._export_data = {"n_cells": len(cells), "cell_sets": set_names[:2],
                             "phase_counts": {name: int((phase == i).sum()) for i, name in enumerate(["S", "G2M"])},
                             "ctrl_size": ctrl_size, "n_bins": n_bins}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
