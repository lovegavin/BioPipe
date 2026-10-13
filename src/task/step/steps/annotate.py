# src/task/step/steps/annotate.py
"""Attach reference fields onto a target by key label.

Aligns two forms on a shared key dimension by label, then copies the
requested reference fields into the target's ``info``, declaring them
parallel to the target key axis.

A reference field may come from either:

* a data column: its label on ``field_dim``; encoded columns carry
  their encoder across so codes stay comparable.
* an info field: declared parallel to ``source_dim`` in
  ``axis_info``; typically read verbatim by ``info_columns``.

This is the standard way to enrich a table with an external lookup
table (variant annotations, gene descriptions, taxon metadata,
sample covariates) without merging data dimensions.

Layout
------
    target     dims: [key_dim, ...]
    reference  dims: [key_dim_ref, field_dim]
    output     dims: same as target

Alignment
---------
Matching is by label, not by position. For every target label on
``target_dim``, the reference row whose ``source_dim`` label equals
it supplies the values. Target labels without a reference match get
NaN.

The alignment is computed once as a position lookup array and applied
with numpy fancy indexing, so the cost is O(n) in C, not in Python.

Params:
    target_dim : key dimension on the target (required)
    source_dim : key dimension on the reference (required)
    fields     : reference field names to attach (required)
    field_dim  : reference data dimension (default: the other 2D dim)
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class AnnotateStep(Step):
    """Attach reference fields onto a target by key label."""

    name = "annotate"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(dims=[param("target_dim")]),
        port(ndim=2, dims=[param("source_dim")]),
    ]
    output_contract = {"mode": "unknown"}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "target_dim": {
                "type": "string",
                "title": "Target key dimension",
                "description": "Dimension on the target form to align on.",
            },
            "source_dim": {
                "type": "string",
                "title": "Reference key dimension",
                "description": "Dimension on the reference form to align on.",
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "title": "Fields to attach",
                "minItems": 1,
                "description": (
                    "Names of reference data columns or reference info "
                    "fields. Data columns are looked up by their label "
                    "on the field dimension; info fields must be "
                    "declared parallel to the source key dimension."
                ),
            },
            "field_dim": {
                "type": "string",
                "title": "Reference field dimension",
            },
            "output": {
                "type": "string",
                "title": "Output key",
            },
        },
        "required": ["target_dim", "source_dim", "fields"],
    }

    def run(self, ctx: Context, inputs) -> None:
        target, reference = inputs
        target_dim = ctx.step_params.get("target_dim")
        source_dim = ctx.step_params.get("source_dim")
        fields = ctx.step_params.get("fields")
        out_name = ctx.step_params.get("output", self.name)

        if not target_dim:
            raise StepError("annotate: 'target_dim' is required")
        if not source_dim:
            raise StepError("annotate: 'source_dim' is required")
        if not fields:
            raise StepError("annotate: 'fields' is required")

        if target_dim not in target.dims:
            raise StepError(
                f"annotate: target_dim '{target_dim}' not present. "
                f"Target dims: {target.dims}"
            )
        if source_dim not in reference.dims:
            raise StepError(
                f"annotate: source_dim '{source_dim}' not present. "
                f"Reference dims: {reference.dims}"
            )
        if reference.data.ndim != 2:
            raise StepError(
                f"annotate: reference must be 2D, "
                f"got ndim={reference.data.ndim}"
            )

        field_dim = ctx.step_params.get("field_dim")
        if field_dim is None:
            other = [d for d in reference.dims if d != source_dim]
            if len(other) != 1:
                raise StepError(
                    f"annotate: cannot infer field_dim from "
                    f"{reference.dims}; specify 'field_dim'"
                )
            field_dim = other[0]
        if field_dim not in reference.dims:
            raise StepError(
                f"annotate: field_dim '{field_dim}' not present. "
                f"Reference dims: {reference.dims}"
            )
        if field_dim == source_dim:
            raise StepError(
                "annotate: field_dim and source_dim must differ"
            )

        ref_field_labels = reference.labels.get(field_dim, {})
        ref_parallel = reference.axis_info.get(source_dim, [])

        field_sources: dict[str, tuple[str, object]] = {}
        for field in fields:
            if field in ref_field_labels:
                field_sources[field] = ("data", ref_field_labels[field])
            elif field in ref_parallel:
                field_sources[field] = ("info", field)
            else:
                raise StepError(
                    f"annotate: field '{field}' is neither a column "
                    f"label on '{field_dim}' "
                    f"({sorted(ref_field_labels)}) nor an info field "
                    f"parallel to '{source_dim}' ({ref_parallel})"
                )

        target_labels = target.labels[target_dim]
        source_labels = reference.labels[source_dim]

        target_axis = target.dims.index(target_dim)
        source_axis = reference.dims.index(source_dim)
        field_axis = reference.dims.index(field_dim)

        target_size = target.data.shape[target_axis]
        source_size = reference.data.shape[source_axis]

        # --- Build a position lookup: target position -> source position. ---
        lookup = np.full(target_size, -1, dtype=np.int64)
        if source_size <= target_size:
            for label, src_pos in source_labels.items():
                tgt_pos = target_labels.get(label)
                if tgt_pos is not None:
                    lookup[tgt_pos] = src_pos
        else:
            for label, tgt_pos in target_labels.items():
                src_pos = source_labels.get(label)
                if src_pos is not None:
                    lookup[tgt_pos] = src_pos

        valid = lookup >= 0
        n_matched = int(valid.sum())
        n_unmatched = target_size - n_matched
        matched_lookup = lookup[valid]

        # Reorient reference so axis 0 is source_dim and axis 1 is field_dim.
        ref_data = np.moveaxis(
            reference.data, (source_axis, field_axis), (0, 1)
        )

        ref_encoders = reference.info.get("encoders", {}).get(
            field_dim, {}
        )

        new_info = dict(target.info)
        new_axis_info = {
            k: list(v) for k, v in target.axis_info.items()
        }
        parallel = set(new_axis_info.get(target_dim, []))
        encoders_out = {
            d: dict(cols)
            for d, cols in new_info.get("encoders", {}).items()
        }

        encoded_fields: list[str] = []

        for field in fields:
            source_kind, source_key = field_sources[field]

            if source_kind == "data":
                column = np.asarray(
                    ref_data[:, source_key], dtype=np.float64
                )
                encoder = ref_encoders.get(field)
            else:
                raw = reference.info.get(field)
                if raw is None:
                    raise StepError(
                        f"annotate: info['{field}'] missing from "
                        f"reference"
                    )
                if isinstance(raw, np.ndarray):
                    column = raw.astype(np.float64, copy=False)
                else:
                    column = pd.to_numeric(
                        pd.Series(raw), errors="coerce"
                    ).to_numpy(dtype=np.float64)
                encoder = None

            values = np.full(target_size, np.nan, dtype=np.float64)
            if n_matched:
                values[valid] = column[matched_lookup]

            new_info[field] = values
            if encoder is not None:
                encoders_out.setdefault(target_dim, {})[field] = encoder
                encoded_fields.append(field)
            parallel.add(field)

        new_axis_info[target_dim] = sorted(parallel)

        if encoders_out:
            new_info["encoders"] = {
                d: c for d, c in encoders_out.items() if c
            }
        else:
            new_info.pop("encoders", None)

        out_form = Form(
            data=target.data.copy(),
            dims=list(target.dims),
            labels={k: dict(v) for k, v in target.labels.items()},
            info=new_info,
            axis_info=new_axis_info,
        )
        out_form.validate()
        ctx[out_name] = out_form

        unmatched_indices = np.where(~valid)[0]
        pos_to_label = {v: k for k, v in target_labels.items()}
        unmatched_labels = [
            pos_to_label[int(i)]
            for i in unmatched_indices
            if int(i) in pos_to_label
        ]

        self._export_data = {
            "target_dim": target_dim,
            "source_dim": source_dim,
            "field_dim": field_dim,
            "fields": list(fields),
            "field_sources": {
                f: field_sources[f][0] for f in fields
            },
            "n_target": int(target_size),
            "n_matched": n_matched,
            "n_unmatched": n_unmatched,
            "encoded_fields": encoded_fields,
            "unmatched_labels": unmatched_labels,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "target_dim": target_dim,
            "fields": list(fields),
            "n_matched": n_matched,
            "n_unmatched": n_unmatched,
        }

        print(
            f"[annotate] '{target_dim}' <- '{source_dim}' "
            f"{n_matched}/{target_size} matched "
            f"({n_unmatched} missing)"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data