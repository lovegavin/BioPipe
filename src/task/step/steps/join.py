# src/task/step/steps/join.py
"""Join two forms along a shared dim by label.

Attaches selected columns from a "metadata" form to a "data" form.
Both forms must have the shared dim as their first axis. The
columns of the metadata form are appended to the data form's second
axis, so the output is a wider form whose labels combine the two.

This is the natural way to bring grouping columns next to the
values they describe, e.g. to color a scatter plot, to split a
barplot, or to feed a violin plot.

Alignment
---------
    inner   keep rows whose label is present in both forms
    left    keep rows whose label is present in the data form,
            filling meta cells with NaN when the row is missing
            from the metadata form

Both forms must be 2D with the shared dim as the first axis. To use
a form whose shared dim is second, transpose it first.

Output
------
    dims    = [shared_dim, <data_other_dim>]
    labels  = {shared_dim:  <common row labels>,
               <data_other_dim>: {<data_feature>: pos,
                                  <selected_meta_column>: pos, ...}}

Feature labels that already exist in the data form are rejected
unless a ``prefix`` is given.

Params:
    dim      : shared dim name (required)
    columns  : list of column labels from the metadata to attach,
               or "all" (default "all")
    how      : "inner" | "left" (default "inner")
    prefix   : optional string prepended to attached column names
    output   : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.core.forms.metadata import project_metadata
from src.task.step.base import Step
from src.task.step.steps._microbiome import CONTRACTS, SCHEMAS, estimate, metadata


class JoinStep(Step):
    """Join two forms along a shared dim by label."""

    name = "join"
    inputs_arity = 2
    outputs = []
    title = 'Join'
    category = "Microbiome"
    builtin_package = "biopipe-microbiome"
    legacy_parameters = False
    parameters_schema = SCHEMAS['join']
    input_contracts, output_contract = CONTRACTS['join']
    output_parameter = "output"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        data_form, meta_form = inputs
        dim = ctx.step_params.get("dim")
        columns = ctx.step_params.get("columns", "all")
        how = ctx.step_params.get("how", "inner")
        prefix = ctx.step_params.get("prefix", "")
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("join: 'dim' is required")
        if how not in ("inner", "left"):
            raise StepError(
                f"join: how must be 'inner' or 'left', got {how!r}"
            )
        if data_form.data.ndim != 2:
            raise StepError(
                f"join: data form must be 2D, "
                f"got ndim={data_form.data.ndim}"
            )
        if meta_form.data.ndim != 2:
            raise StepError(
                f"join: metadata form must be 2D, "
                f"got ndim={meta_form.data.ndim}"
            )
        if data_form.dims[0] != dim:
            raise StepError(
                f"join: data's first dim must be '{dim}', "
                f"got '{data_form.dims[0]}'. Use transpose if needed."
            )
        if meta_form.dims[0] != dim:
            raise StepError(
                f"join: metadata's first dim must be '{dim}', "
                f"got '{meta_form.dims[0]}'. Use transpose if needed."
            )

        data_other_dim = data_form.dims[1]
        meta_other_dim = meta_form.dims[1]

        data_row_labels = data_form.labels[dim]
        meta_row_labels = meta_form.labels[dim]
        data_feature_labels = data_form.labels[data_other_dim]
        meta_feature_labels = meta_form.labels[meta_other_dim]

        # Row alignment.
        if how == "inner":
            common = [
                l for l in data_row_labels
                if l in meta_row_labels
            ]
        else:  # left
            common = list(data_row_labels.keys())
        if not common:
            raise StepError(
                f"join: no common row labels on '{dim}'"
            )

        # Column selection.
        if columns == "all":
            selected_cols = list(meta_feature_labels.keys())
        elif isinstance(columns, list):
            if not columns:
                raise StepError(
                    "join: 'columns' must be a non-empty list "
                    "or 'all'"
                )
            missing = [
                c for c in columns if c not in meta_feature_labels
            ]
            if missing:
                raise StepError(
                    f"join: columns not found in metadata: "
                    f"{missing[:5]}. Available: "
                    f"{sorted(meta_feature_labels)[:5]}..."
                )
            selected_cols = list(columns)
        else:
            raise StepError(
                "join: 'columns' must be a list or 'all', "
                f"got {type(columns).__name__}"
            )

        # Build the combined feature label map.
        combined_feature = dict(data_feature_labels)
        next_pos = max(combined_feature.values()) + 1 if \
            combined_feature else 0
        attached_names: list[str] = []
        for c in selected_cols:
            key = f"{prefix}{c}" if prefix else c
            if key in combined_feature:
                raise StepError(
                    f"join: feature label '{key}' already exists in "
                    f"data. Use 'prefix' to disambiguate."
                )
            combined_feature[key] = next_pos
            attached_names.append(key)
            next_pos += 1

        n_common = len(common)
        n_data_feat = len(data_feature_labels)
        n_attach = len(attached_names)
        n_out_feat = n_data_feat + n_attach

        out_data = np.full(
            (n_common, n_out_feat), np.nan, dtype=np.float32
        )

        data_fill = data_form.info.get("missing_code", np.nan)
        if not (isinstance(data_fill, float) and np.isnan(data_fill)):
            data_fill_val = float(data_fill)
        else:
            data_fill_val = np.nan

        for i, l in enumerate(common):
            if l in data_row_labels:
                row = data_form.data[data_row_labels[l], :]
                code = data_form.info.get("missing_code", np.nan)
                out_data[i, :n_data_feat] = np.where(row == code, np.nan, row)
            if l in meta_row_labels:
                row = meta_form.data[meta_row_labels[l], :]
                for k, c in enumerate(selected_cols):
                    value = row[meta_feature_labels[c]]
                    code = meta_form.info.get("missing_code", np.nan)
                    out_data[i, n_data_feat + k] = np.nan if value == code else value

        out_labels = {
            dim: {l: i for i, l in enumerate(common)},
            data_other_dim: combined_feature,
        }

        # Encoders: keep data's encoders for the data features, and
        # add the metadata's encoders for the attached columns.
        data_encoders = dict(
            data_form.info.get("encoders", {}).get(
                data_other_dim, {}
            )
        )
        meta_encoders = meta_form.info.get("encoders", {}).get(
            meta_other_dim, {}
        )
        new_encoders = dict(data_encoders)
        encoder_note: list[str] = []
        for c, new_name in zip(selected_cols, attached_names):
            if c in meta_encoders:
                new_encoders[new_name] = meta_encoders[c]
                encoder_note.append(new_name)

        # Keep row annotations aligned to the joined order. Feature-axis
        # annotations gain missing entries for columns introduced by the join.
        out_info, out_axes = project_metadata(data_form, {dim: [data_row_labels[label] for label in common]})
        for field in out_axes.get(data_other_dim, []):
            out_info[field] = list(out_info[field]) + [None] * len(attached_names)
        out_info.update(missing_code=np.nan, representation="joined")
        out_info.pop("ploidy", None)
        out_info.pop("alphabet", None)
        if new_encoders:
            out_info["encoders"] = {data_other_dim: new_encoders}

        ctx[out_name] = Form(
            data=out_data,
            dims=[dim, data_other_dim],
            labels=out_labels,
            info=out_info,
            axis_info=out_axes,
        )

        n_unmatched = sum(
            1 for l in common if l not in meta_row_labels
        )

        self._export_data = {
            "dim": dim,
            "how": how,
            "columns_attached": attached_names,
            "n_rows": n_common,
            "n_data_features": n_data_feat,
            "n_attached_features": n_attach,
            "n_output_features": n_out_feat,
            "n_unmatched_rows": n_unmatched,
            "encoder_features": encoder_note,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "how": how,
            "n_rows": n_common,
            "n_attached": n_attach,
            "n_unmatched": n_unmatched,
        }

        print(
            f"[join] dim='{dim}' how='{how}' "
            f"data={data_form.data.shape} + meta_cols={n_attach} "
            f"-> {out_data.shape}"
            + (f" ({n_unmatched} unmatched)" if n_unmatched else "")
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data