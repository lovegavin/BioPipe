# src/task/step/steps/combat.py
"""Batch correction with ComBat or per-batch mean centering.

ComBat is the empirical-Bayes location/scale correction from Johnson et
al. (2007), exposed through Scanpy's implementation. ``mean_center`` is
the simpler location-only baseline: subtract each batch's feature mean
and add the overall feature mean.

The metadata table supplies one batch label per expression sample. All
expression samples must be present in the metadata; extra metadata rows
are ignored. Non-finite expression values are rejected rather than
silently corrected.
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


class CombatStep(Step):
    name = "combat"
    title = "Batch correction"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scanpy>=1.10", "anndata>=0.10"]
    dependency_imports = ["scanpy", "anndata"]
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        {**port(ndim=2, dims=[param("sample_dim", "sample")]), "labels_any": [param("batch_label")]},
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "batch_label": {"type": "string"},
            "method": {"type": "string", "enum": ["combat", "mean_center"], "default": "combat"},
            "output": {"type": "string"},
        },
        "required": ["batch_label"],
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        batch_label = ctx.step_params["batch_label"]
        method = ctx.step_params.get("method", "combat")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(expr, feature_dim, sample_dim, label="expression")
        require_dims(meta, sample_dim, label="metadata")
        if method not in ("combat", "mean_center"):
            raise StepError("combat: method must be 'combat' or 'mean_center'")
        data = reorder(expr, feature_dim, sample_dim)
        features = labels_in_order(expr, feature_dim)
        samples = labels_in_order(expr, sample_dim)
        if not np.isfinite(data).all():
            raise StepError("combat: expression matrix contains non-finite values")
        meta_samples, values = group_values(meta, sample_dim, batch_label)
        by_sample = {sample: str(value) for sample, value in zip(meta_samples, values)}
        missing = [sample for sample in samples if sample not in by_sample]
        if missing:
            raise StepError(f"combat: {len(missing)} expression samples have no batch label")
        batch_values = [by_sample[sample] for sample in samples]
        batch_names: list[str] = []
        batch_index: dict[str, int] = {}
        codes = np.empty(len(samples), dtype=np.int64)
        for i, value in enumerate(batch_values):
            if value not in batch_index:
                batch_index[value] = len(batch_names)
                batch_names.append(value)
            codes[i] = batch_index[value]
        if len(batch_names) < 2:
            raise StepError("combat: at least two batches are required")
        if method == "mean_center":
            corrected = data.copy()
            overall = data.mean(axis=1, keepdims=True)
            for b in range(len(batch_names)):
                columns = codes == b
                corrected[:, columns] -= data[:, columns].mean(axis=1, keepdims=True)
            corrected += overall
        else:
            try:
                import anndata as ad
                import pandas as pd
                import scanpy as sc
            except ImportError as exc:
                raise StepError("combat requires anndata, pandas and scanpy") from exc
            adata = ad.AnnData(
                X=np.asarray(data.T, dtype=np.float32),
                obs=pd.DataFrame({batch_label: [batch_names[i] for i in codes]}, index=samples),
                var=pd.DataFrame(index=features),
            )
            sc.pp.combat(adata, key=batch_label)
            corrected = np.asarray(adata.X, dtype=np.float64).T
        form = make_form(
            corrected, [feature_dim, sample_dim],
            {feature_dim: axis_labels(features, feature_dim),
             sample_dim: axis_labels(samples, sample_dim)},
        )
        ctx[out_name] = form
        sizes = {name: int((codes == i).sum()) for i, name in enumerate(batch_names)}
        self._export_data = {
            "method": method, "batch_label": batch_label,
            "batches": batch_names, "batch_sizes": sizes,
            "n_features": len(features), "n_samples": len(samples),
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method, "n_batches": len(batch_names),
            "n_features": len(features), "n_samples": len(samples),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
