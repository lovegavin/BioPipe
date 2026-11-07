"""Correspondence analysis of a contingency table."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import require_dims


class CorrespStep(Step):
    provider = "operon-core"
    parameters_file = "corresp.CorrespStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "corresp",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Correspondence analysis",
        "category": "Statistics",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "info": {},
                        "ndim": 2,
                        "dims": [{"param": "row_dim", "default": "row"},
                                 {"param": "column_dim", "default": "column"}],
                        "labels": [], "parallel": []}],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True,
                                  "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Simple correspondence analysis of a non-negative contingency "
            "table; the row standard coordinates are the output and the "
            "column scores, eigenvalues and proportions are reported in info."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        n_components = int(ctx.step_params.get("n_components", 2))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, row_dim, column_dim, label="corresp")
        if n_components < 1:
            raise StepError("corresp: n_components must be at least one")
        x = np.asarray(form.data, dtype=np.float64)
        axis = form.dims.index(row_dim)
        if axis == 1:
            x = x.T
        if x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 2:
            raise StepError("corresp: need at least two rows and two columns")
        if not np.all(np.isfinite(x)):
            raise StepError("corresp: table contains non-finite values")
        if np.any(x < 0.0):
            raise StepError("corresp: table entries must be non-negative")
        total = float(x.sum())
        if total <= 0.0:
            raise StepError("corresp: all frequencies are zero")
        row_mass = x.sum(axis=1) / total
        col_mass = x.sum(axis=0) / total
        if np.any(row_mass <= 0.0) or np.any(col_mass <= 0.0):
            raise StepError("corresp: empty row or column in table")
        residual = x / total - np.outer(row_mass, col_mass)
        inv_row = 1.0 / np.sqrt(row_mass)
        inv_col = 1.0 / np.sqrt(col_mass)
        standard = (residual * inv_row[:, None]) * inv_col[None, :]
        u, singular, vt = np.linalg.svd(standard, full_matrices=False)
        nf = min(n_components, int(singular.size))
        if nf < 1 or singular[0] <= 0.0:
            raise StepError("corresp: table has zero inertia")
        rows = u[:, :nf] * inv_row[:, None]
        columns = vt[:nf].T * inv_col[:, None]
        inertia = float(np.sum(singular ** 2))
        row_labels = [k for k, _ in sorted(form.labels[row_dim].items(),
                                          key=lambda kv: kv[1])]
        col_labels = [k for k, _ in sorted(form.labels[column_dim].items(),
                                          key=lambda kv: kv[1])]
        if x.shape[0] != len(row_labels):
            raise StepError("corresp: row label count does not match the table")
        if x.shape[1] != len(col_labels):
            raise StepError("corresp: column label count does not match the table")
        components = [f"CA{i + 1}" for i in range(nf)]
        data = np.asarray(rows, dtype=np.float32)
        ctx[out_name] = Form(
            data=data,
            dims=[row_dim, "component"],
            labels={row_dim: {name: i for i, name in enumerate(row_labels)},
                    "component": {name: i for i, name in enumerate(components)}},
            info={"missing_code": np.nan,
                  "column_labels": col_labels,
                  "column_scores": columns.tolist(),
                  "eigenvalues": singular[:nf].tolist(),
                  "proportions": (singular[:nf] ** 2 / inertia).tolist(),
                  "total_inertia": inertia,
                  "n_components": nf},
        )
        self._export_data = {
            "eigenvalues": singular[:nf].tolist(),
            "total_inertia": inertia,
            "column_scores": columns.tolist(),
        }
        print(f"[{self.name}] inertia={inertia:.6f} components={nf}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
