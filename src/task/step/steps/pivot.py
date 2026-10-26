# src/task/step/steps/pivot.py
"""Turn a long table into a wide matrix by two categorical columns.

The input is a 2D form whose ``field_dim`` holds a set of named
columns. Two of those columns are chosen: one becomes the row axis
of the output, the other becomes the column axis. A third column may
supply the cell value; without it, every observed pair contributes 1.

This is the standard way to build a gene x GO-term membership matrix
from a GAF file, a sample x feature matrix from a long CSV, or any
pair-count table that downstream matrix operators can consume.

Layout
------
    input   dims: [pair, field]
    output  dims: [<index_name>, <columns_name>]

Duplicate (index, column) pairs are combined by ``agg``.

A hard cell-count cap protects the runtime from accidentally
materialising a huge dense matrix. When the cap is exceeded, filter
the input to a smaller subset before pivoting.

Params:
    index_label   : column label on the input field dim, becomes the
                    row axis (required)
    columns_label : column label on the input field dim, becomes the
                    column axis (required)
    values_label  : column label supplying cell values; without it
                    every observed pair contributes 1
    index_name    : name of the output row dim (default: index_label)
    columns_name  : name of the output column dim (default: columns_label)
    agg           : sum | first | max | min | count (default sum)
    output        : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_AGGS = ("sum", "first", "max", "min", "count")
# Hard cap on dense output cells (~800 MB at float32).
_MAX_CELLS = 200_000_000_0


class PivotStep(Step):
    """Pivot a long 2D table into a wide matrix by two categorical columns."""
    provider = 'biopipe-core'
    parameters_file = 'pivot.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'pivot',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'pivot',
     'description': 'Pivot a long 2D table into a wide matrix by two categorical columns.',
     'category': 'data',
     'icon': 'Columns',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        if form.data.ndim != 2:
            raise StepError(
                f"pivot: input must be 2D, got ndim={form.data.ndim}"
            )

        index_label = ctx.step_params.get("index_label")
        columns_label = ctx.step_params.get("columns_label")
        values_label = ctx.step_params.get("values_label")
        index_name = ctx.step_params.get("index_name") or index_label
        columns_name = ctx.step_params.get("columns_name") or columns_label
        agg = ctx.step_params.get("agg", "sum")
        out_name = ctx.step_params.get("output", self.name)

        if not index_label:
            raise StepError("pivot: 'index_label' is required")
        if not columns_label:
            raise StepError("pivot: 'columns_label' is required")
        if agg not in _AGGS:
            raise StepError(
                f"pivot: agg must be one of {list(_AGGS)}, got {agg!r}"
            )
        if index_name == columns_name:
            raise StepError(
                f"pivot: index_name and columns_name must differ "
                f"(both '{index_name}')"
            )

        row_dim, field_dim = form.dims
        field_labels = form.labels.get(field_dim, {})

        for label in (index_label, columns_label):
            if label not in field_labels:
                raise StepError(
                    f"pivot: label '{label}' not in field labels "
                    f"{sorted(field_labels)}"
                )
        if values_label and values_label not in field_labels:
            raise StepError(
                f"pivot: values_label '{values_label}' not in field "
                f"labels {sorted(field_labels)}"
            )

        index_codes = form.data[:, field_labels[index_label]]
        columns_codes = form.data[:, field_labels[columns_label]]

        if values_label:
            values = form.data[
                :, field_labels[values_label]
            ].astype(np.float64)
        else:
            values = np.ones(form.data.shape[0], dtype=np.float64)

        encoders_for_field = form.info.get("encoders", {}).get(
            field_dim, {}
        )

        index_strings = _decode(
            index_codes, encoders_for_field.get(index_label)
        )
        columns_strings = _decode(
            columns_codes, encoders_for_field.get(columns_label)
        )

        frame = pd.DataFrame({
            "index": index_strings,
            "column": columns_strings,
            "value": values,
        })

        agg_func = {
            "sum": "sum",
            "first": "first",
            "max": "max",
            "min": "min",
            "count": "size",
        }[agg]

        try:
            grouped = frame.groupby(
                ["index", "column"], sort=False, dropna=False
            )["value"]
            if agg == "count":
                wide = grouped.size().unstack(fill_value=0)
            else:
                wide = grouped.agg(agg_func).unstack(fill_value=0)
        except (ValueError, KeyError) as exc:
            raise StepError(f"pivot: aggregation failed: {exc}") from exc

        n_index = int(wide.shape[0])
        n_columns = int(wide.shape[1])

        if n_index * n_columns > _MAX_CELLS:
            raise StepError(
                f"pivot: output would be {n_index} x {n_columns} "
                f"= {n_index * n_columns:,} cells, exceeding the "
                f"{_MAX_CELLS:,} cap. Filter the input to a smaller "
                f"subset before pivoting."
            )

        out_data = wide.to_numpy(dtype=np.float32)

        index_labels = {
            str(label): i for i, label in enumerate(wide.index)
        }
        column_labels = {
            str(label): i for i, label in enumerate(wide.columns)
        }

        out_form = Form(
            data=out_data,
            dims=[index_name, columns_name],
            labels={
                index_name: index_labels,
                columns_name: column_labels,
            },
            info={"missing_code": np.nan},
        )
        out_form.validate()
        ctx[out_name] = out_form

        nonzero = int(np.count_nonzero(out_data))

        self._export_data = {
            "index_label": index_label,
            "columns_label": columns_label,
            "values_label": values_label,
            "index_name": index_name,
            "columns_name": columns_name,
            "agg": agg,
            "n_input_rows": int(form.data.shape[0]),
            "n_index": n_index,
            "n_columns": n_columns,
            "n_cells": n_index * n_columns,
            "n_nonzero": nonzero,
            "sparsity": (
                1.0 - nonzero / (n_index * n_columns)
                if n_index * n_columns else 0.0
            ),
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "index_name": index_name,
            "columns_name": columns_name,
            "shape": [n_index, n_columns],
        }

        print(
            f"[pivot] {form.data.shape} -> ({n_index}, {n_columns}) "
            f"[{index_name} x {columns_name}], agg={agg}, "
            f"nonzero={nonzero}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _decode(codes, encoder) -> list[str]:
    if encoder is None:
        return [str(int(round(float(c)))) for c in codes]
    inverse = getattr(encoder, "inverse", {})
    out = []
    for c in codes:
        key = int(round(float(c)))
        out.append(str(inverse.get(key, key)))
    return out
