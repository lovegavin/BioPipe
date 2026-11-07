"""NODF nestedness of a binary community matrix."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._ext_common import require_dims


def _paired(counts, fill, matrix, row_axis):
    n = matrix.shape[0] if row_axis else matrix.shape[1]
    out = np.zeros(n * (n - 1) // 2, dtype=np.float64)
    counter = 0
    for i in range(n - 1):
        first = matrix[i, :] if row_axis else matrix[:, i]
        for j in range(i + 1, n):
            counter += 1
            if fill[i] <= fill[j] or fill[i] == 0.0 or fill[j] == 0.0:
                continue
            second = matrix[j, :] if row_axis else matrix[:, j]
            out[counter - 1] = np.sum((first + second) == 2) / fill[j]
    return out


class NestednessStep(Step):
    provider = "operon-core"
    parameters_file = "nestedness.NestednessStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "nestedness",
        "version": "1.0.0",
        "kind": "operator",
        "title": "NODF nestedness",
        "category": "Statistics",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "info": {},
                        "ndim": 2,
                        "dims": [{"param": "sample_dim", "default": "sample"},
                                 {"param": "taxon_dim", "default": "taxon"}],
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
            "Nestedness by overlap and decreasing fill (NODF) for a binary "
            "sample-by-taxon matrix, following the vegan nestednodf definition."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        taxon_dim = ctx.step_params.get("taxon_dim", "taxon")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, sample_dim, taxon_dim, label="nestedness")
        data = np.asarray(form.data)
        axis = form.dims.index(sample_dim)
        if axis == 1:
            data = data.T
        if data.ndim != 2 or data.shape[0] < 2 or data.shape[1] < 2:
            raise StepError("nestedness: need at least two rows and two columns")
        if not np.all(np.isfinite(data.astype(float))):
            raise StepError("nestedness: matrix contains non-finite values")
        binary = np.where(np.asarray(data, dtype=np.float64) > 0.0, 1.0, 0.0)
        row_fill = binary.sum(axis=1)
        col_fill = binary.sum(axis=0)
        total = float(binary.sum())
        if total <= 0.0:
            raise StepError("nestedness: matrix has no occupied cells")
        row_order = np.argsort(-row_fill, kind="stable")
        col_order = np.argsort(-col_fill, kind="stable")
        matrix = binary[row_order][:, col_order]
        row_fill = row_fill[row_order]
        col_fill = col_fill[col_order]
        paired_rows = _paired(row_fill, row_fill, matrix, True)
        paired_cols = _paired(col_fill, col_fill, matrix.T, True)
        nr, nc = matrix.shape
        n_columns = float(paired_cols.mean() * 100.0) if paired_cols.size else 0.0
        n_rows = float(paired_rows.mean() * 100.0) if paired_rows.size else 0.0
        possible = nc * (nc - 1) / 2.0 + nr * (nr - 1) / 2.0
        nodf = float((paired_rows.sum() + paired_cols.sum()) * 100.0 / possible)
        fill = float(row_fill.sum() / (nr * nc))
        row_names = [k for k, _ in sorted(form.labels[sample_dim].items(),
                                         key=lambda kv: kv[1])]
        col_names = [k for k, _ in sorted(form.labels[taxon_dim].items(),
                                         key=lambda kv: kv[1])]
        if axis == 1:
            row_names, col_names = col_names, row_names
        data_out = np.asarray([[n_columns], [n_rows], [nodf], [fill]], dtype=np.float32)
        ctx[out_name] = Form(
            data=data_out,
            dims=["statistic", "value"],
            labels={"statistic": {"N.columns": 0, "N.rows": 1,
                                  "NODF": 2, "fill": 3},
                    "value": {"value": 0}},
            info={"missing_code": np.nan, "method": "nestednodf",
                  "rows": [row_names[int(i)] for i in row_order],
                  "columns": [col_names[int(i)] for i in col_order]},
        )
        self._export_data = {
            "N.columns": n_columns,
            "N.rows": n_rows,
            "NODF": nodf,
            "fill": fill,
        }
        print(f"[{self.name}] NODF={nodf:.3f} fill={fill:.3f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
