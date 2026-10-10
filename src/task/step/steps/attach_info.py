# src/task/step/steps/attach_info.py
"""Attach axis-parallel info arrays from a source form onto a target.

The source declares which info keys are parallel to which axis via
``axis_info``. This step reads those arrays, aligns them to the
target axis by label, and stores the result as target info entries
declared parallel to the target dim.

Data is never modified.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.reader.readers._encoder import get_encoder
from src.task.context import Context
from src.task.step.base import Step


class AttachInfoStep(Step):
    """Attach source info arrays to a target dimension.

    Inputs:
        target : form to attach onto
        source : form whose info holds the arrays

    Params:
        fields     : list of info keys to attach
        target_dim : dimension of the target to align against
        output     : context key for the result
    """

    name = "attach_info"
    inputs_arity = 2
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        target, source = inputs
        fields = list(ctx.step_params["fields"])
        target_dim = ctx.step_params["target_dim"]
        out_name = ctx.step_params.get("output", self.name)

        if target_dim not in target.dims:
            raise StepError(
                f"attach_info: target_dim '{target_dim}' not present. "
                f"Target dims: {target.dims}"
            )

        # source_dim is derived from source.axis_info; must be unique.
        source_dims: dict[str, str] = {}
        for f in fields:
            if f not in source.info:
                raise StepError(
                    f"attach_info: field '{f}' not in source.info. "
                    f"Available: {sorted(source.info)}"
                )
            matches = [
                dim for dim, keys in source.axis_info.items()
                if f in keys
            ]
            if not matches:
                raise StepError(
                    f"attach_info: field '{f}' is not declared parallel "
                    f"to any dim in source.axis_info"
                )
            if len(matches) > 1:
                raise StepError(
                    f"attach_info: field '{f}' is parallel to multiple "
                    f"source dims: {matches}"
                )
            source_dims[f] = matches[0]

        # All fields must come from the same source dim.
        unique_source_dims = set(source_dims.values())
        if len(unique_source_dims) != 1:
            raise StepError(
                f"attach_info: fields come from different source dims: "
                f"{source_dims}. Split into separate calls."
            )
        source_dim = unique_source_dims.pop()

        source_size = source.data.shape[source.dims.index(source_dim)]
        for f in fields:
            arr = source.info[f]
            if len(arr) != source_size:
                raise StepError(
                    f"attach_info: source.info['{f}'] has length "
                    f"{len(arr)} but source dim '{source_dim}' has "
                    f"size {source_size}"
                )

        source_labels = source.labels[source_dim]
        target_labels = target.labels[target_dim]

        lookup: list[int | None] = [
            source_labels.get(lab) for lab in target_labels
        ]

        new_info = {k: v for k, v in target.info.items()}
        new_axis_info = {
            k: list(v) for k, v in target.axis_info.items()
        }
        target_parallel = set(new_axis_info.get(target_dim, []))

        encoded_fields: list[str] = []

        for f in fields:
            arr = source.info[f]
            raw = [
                arr[p] if p is not None else None for p in lookup
            ]

            numeric = True
            try:
                _ = np.array(
                    [v if v is not None else np.nan for v in raw],
                    dtype=np.float32,
                )
            except (ValueError, TypeError):
                numeric = False

            if not numeric:
                encoder = get_encoder("labelencoder")
                str_vals = [
                    str(v) if v is not None else "__missing__"
                    for v in raw
                ]
                encoder.fit_transform(str_vals)
                existing = dict(new_info.get("encoders", {}))
                existing.setdefault(target_dim, {})[f] = encoder
                new_info["encoders"] = existing
                encoded_fields.append(f)

            new_info[f] = list(raw)
            target_parallel.add(f)

        new_axis_info[target_dim] = sorted(target_parallel)

        new_form = Form(
            data=target.data.copy(),
            dims=list(target.dims),
            labels={k: dict(v) for k, v in target.labels.items()},
            info=new_info,
            axis_info=new_axis_info,
        )
        new_form.validate()
        ctx[out_name] = new_form

        n_matched = sum(1 for p in lookup if p is not None)
        n_unmatched = len(lookup) - n_matched

        self._export_data = {
            "fields": fields,
            "target_dim": target_dim,
            "source_dim": source_dim,
            "target_shape": list(target.data.shape),
            "n_target_labels": len(lookup),
            "n_matched": n_matched,
            "n_unmatched": n_unmatched,
            "encoded_fields": encoded_fields,
        }

        print(
            f"[attach_info] attached {len(fields)} field(s) "
            f"from '{source_dim}' to '{target_dim}' "
            f"({n_matched} matched, {n_unmatched} unmatched)"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data