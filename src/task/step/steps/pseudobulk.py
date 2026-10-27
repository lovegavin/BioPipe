# src/task/step/steps/pseudobulk.py
"""Aggregate single cells into sample/group-level pseudobulk profiles.

This is the standard pseudobulk operation: cells are grouped by a
metadata column, then summed or averaged per gene. It is deliberately
separate from differential expression; downstream tests decide whether
the pseudobulk matrix is used with limma/DESeq2 or descriptive plots.

Shared genes are kept in the input order; cells absent from metadata
are rejected rather than silently dropped.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import (
    axis_labels,
    group_values,
    labels_in_order,
    make_form,
    reorder,
    require_dims,
)


class PseudobulkStep(Step):
    name = "pseudobulk"
    title = "Pseudobulk aggregation"
    category = "Analysis"
    builtin_package = "biopipe-core"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("cell_dim", "cell"), param("gene_dim", "gene")]),
        {**port(ndim=2, dims=[param("cell_dim", "cell")]), "labels_any": [param("group_label")]},
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "cell_dim": {"type": "string", "default": "cell"},
            "gene_dim": {"type": "string", "default": "gene"},
            "group_label": {"type": "string"},
            "method": {"type": "string", "enum": ["sum", "mean"], "default": "sum"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
    }

    def run(self, ctx: Context, inputs) -> None:
        counts, meta = inputs
        cell_dim = ctx.step_params.get("cell_dim", "cell")
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        group_label = ctx.step_params["group_label"]
        method = ctx.step_params.get("method", "sum")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(counts, cell_dim, gene_dim, label="counts")
        if method not in ("sum", "mean"):
            raise StepError("pseudobulk: method must be 'sum' or 'mean'")
        require_dims(meta, cell_dim, label="metadata")
        meta_cells, values = group_values(meta, cell_dim, group_label)
        values = np.asarray(values)
        if len(values) != len(meta_cells):
            raise StepError("pseudobulk: group column is not parallel to the cell axis")
        counts_cells = labels_in_order(counts, cell_dim)
        counts_pos = {cell: i for i, cell in enumerate(counts_cells)}
        missing = [cell for cell in meta_cells if cell not in counts_pos]
        if missing:
            raise StepError(f"pseudobulk: {len(missing)} metadata cells are absent from counts")
        genes = labels_in_order(counts, gene_dim)
        data = reorder(counts, cell_dim, gene_dim)
        groups: list[str] = []
        members: list[list[int]] = []
        group_index: dict[str, int] = {}
        for cell, value in zip(meta_cells, values):
            key = str(value)
            if key not in group_index:
                group_index[key] = len(groups)
                groups.append(key)
                members.append([])
            members[group_index[key]].append(counts_pos[cell])
        out = np.empty((len(groups), len(genes)), dtype=np.float64)
        for i, indices in enumerate(members):
            block = data[indices, :]
            out[i, :] = block.sum(axis=0) if method == "sum" else block.mean(axis=0)
        form = make_form(
            out, [group_label, gene_dim],
            {group_label: axis_labels(groups, group_label),
             gene_dim: dict(counts.labels[gene_dim])},
        )
        ctx[out_name] = form
        self._export_data = {
            "groups": groups, "n_groups": len(groups), "n_genes": len(genes),
            "cells_per_group": {name: len(members[i]) for i, name in enumerate(groups)},
            "method": method,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_groups": len(groups), "n_genes": len(genes), "method": method,
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
