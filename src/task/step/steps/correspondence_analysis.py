"""Correspondence analysis of a two-way contingency table."""
from __future__ import annotations

import numpy as np
from scipy.stats import chi2 as chi2_distribution

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import ordered_labels


class CorrespondenceAnalysisStep(Step):
    """Row and column principal coordinates from a contingency table."""

    name = "correspondence_analysis"
    title = "Correspondence analysis"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26", "scipy>=1.11"]
    dependency_imports = ["numpy", "scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("row_dim", "row"), param("column_dim", "column")],
        )
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "row_dim": {"type": "string", "default": "row"},
            "column_dim": {"type": "string", "default": "column"},
            "n_components": {"type": "integer", "minimum": 1, "default": 2},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        row_dim = ctx.step_params.get("row_dim", "row")
        column_dim = ctx.step_params.get("column_dim", "column")
        if row_dim not in form.dims or column_dim not in form.dims:
            raise StepError(
                f"{self.name}: expected dims {row_dim!r}, {column_dim!r}, "
                f"got {form.dims}"
            )
        data = np.asarray(form.data, dtype=np.float64)
        if data.ndim != 2:
            raise StepError(f"{self.name}: input must be 2D")
        if form.dims.index(row_dim) == 1:
            data = data.T
        row_names = ordered_labels(form, row_dim)
        column_names = ordered_labels(form, column_dim)
        if data.shape != (len(row_names), len(column_names)):
            raise StepError(f"{self.name}: labels do not match the table shape")
        if not np.isfinite(data).all():
            raise StepError(f"{self.name}: table must be finite")
        if np.any(data < 0):
            raise StepError(f"{self.name}: counts must be nonnegative")
        row_mass = data.sum(axis=1)
        column_mass = data.sum(axis=0)
        total = float(data.sum())
        if total <= 0:
            raise StepError(f"{self.name}: table is empty")
        if np.any(row_mass <= 0) or np.any(column_mass <= 0):
            raise StepError(f"{self.name}: every row and column needs a positive margin")
        if data.shape[0] < 2 or data.shape[1] < 2:
            raise StepError(f"{self.name}: at least two rows and two columns are required")

        row_share = row_mass / total
        column_share = column_mass / total
        expected = np.outer(row_share, column_share)
        standardized = (data / total - expected) / np.sqrt(expected)
        u_matrix, all_singular, vt_matrix = np.linalg.svd(
            standardized, full_matrices=False
        )
        max_components = min(data.shape[0] - 1, data.shape[1] - 1)
        requested = int(ctx.step_params.get("n_components", 2))
        components = min(requested, max_components)
        if components < 1:
            raise StepError(f"{self.name}: no correspondence components available")

        singular = all_singular[:components]
        standard_rows = u_matrix[:, :components] / np.sqrt(row_share)[:, None]
        standard_columns = vt_matrix.T[:, :components] / np.sqrt(column_share)[:, None]
        principal_rows = standard_rows * singular
        principal_columns = standard_columns * singular
        all_inertia = all_singular ** 2
        inertia = all_inertia[:components]
        total_inertia = float(np.sum(all_inertia))
        if total_inertia <= 0:
            raise StepError(f"{self.name}: table has no correspondence inertia")

        # Full-dimensional squared distances are needed for cos2 even when
        # only the leading components are returned.
        full_rows = (u_matrix / np.sqrt(row_share)[:, None]) * all_singular
        full_columns = (
            vt_matrix.T / np.sqrt(column_share)[:, None]
        ) * all_singular
        row_distance = np.sum(full_rows ** 2, axis=1)
        column_distance = np.sum(full_columns ** 2, axis=1)

        row_contribution = (
            row_share[:, None] * principal_rows ** 2 / inertia[None, :]
        )
        column_contribution = (
            column_share[:, None] * principal_columns ** 2 / inertia[None, :]
        )
        row_cos2 = np.divide(
            principal_rows ** 2,
            row_distance[:, None],
            out=np.zeros_like(principal_rows),
            where=row_distance[:, None] > 0,
        )
        column_cos2 = np.divide(
            principal_columns ** 2,
            column_distance[:, None],
            out=np.zeros_like(principal_columns),
            where=column_distance[:, None] > 0,
        )

        point_names = [f"row:{name}" for name in row_names] + [
            f"column:{name}" for name in column_names
        ]
        coordinates = np.vstack([principal_rows, principal_columns])
        out = Form(
            data=coordinates,
            dims=["point", "component"],
            labels={
                "point": {name: index for index, name in enumerate(point_names)},
                "component": {
                    f"PC{index + 1}": index for index in range(components)
                },
            },
            info={
                "method": "correspondence_analysis",
                "n": int(total),
                "n_rows": int(data.shape[0]),
                "n_columns": int(data.shape[1]),
                "total_inertia": total_inertia,
                "chi_square": float(total * total_inertia),
                "df": int((data.shape[0] - 1) * (data.shape[1] - 1)),
                "p_value": float(
                    chi2_distribution.sf(
                        total * total_inertia,
                        (data.shape[0] - 1) * (data.shape[1] - 1),
                    )
                ),
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        explained = inertia / total_inertia
        self._export = {
            "row_labels": row_names,
            "column_labels": column_names,
            "row_mass": [float(value) for value in row_share],
            "column_mass": [float(value) for value in column_share],
            "singular_values": [float(value) for value in singular],
            "inertia": [float(value) for value in inertia],
            "explained": [float(value) for value in explained],
            "cumulative": [float(value) for value in np.cumsum(explained)],
            "total_inertia": total_inertia,
            "chi_square": float(total * total_inertia),
            "df": int((data.shape[0] - 1) * (data.shape[1] - 1)),
            "standard_row_coordinates": standard_rows.tolist(),
            "standard_column_coordinates": standard_columns.tolist(),
            "principal_row_coordinates": principal_rows.tolist(),
            "principal_column_coordinates": principal_columns.tolist(),
            "row_contribution": row_contribution.tolist(),
            "column_contribution": column_contribution.tolist(),
            "row_cos2": row_cos2.tolist(),
            "column_cos2": column_cos2.tolist(),
        }
        print(
            f"[{self.name}] {data.shape[0]}x{data.shape[1]}, "
            f"inertia={total_inertia:.6g}, components={components}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export
