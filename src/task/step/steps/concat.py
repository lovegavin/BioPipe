# src/task/step/steps/concat.py
"""Concat step: stack several forms along one dimension.

Along the axis dim, data is concatenated and labels are merged. When
``align`` is given together with ``label``, the key columns used for
alignment collapse into a single output label: the first input's key
column keeps its position and is renamed to ``label``; the same key
column in every other input is dropped.

On every other shared dim, labels are intersected and every input is
reordered to the first input's order.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class ConcatStep(Step):
    """Concatenate several forms along one dimension.

    Params:

    * ``axis``   — name of the dimension to concatenate along.
    * ``align``  — optional ``{dim: name, key: {input: label}}``.
    * ``label``  — optional name for the merged key column.
    * ``output`` — context key for the result.
    """

    name = "concat"
    inputs_arity = "*"
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        if len(inputs) < 2:
            raise StepError("concat needs at least two inputs")

        axis_name = ctx.step_params["axis"]
        out_name = ctx.step_params["output"]
        align_cfg = ctx.step_params.get("align")
        merged_label = ctx.step_params.get("label")
        input_names = ctx.step_params.get("_input_names", [])

        ref = inputs[0]

        # --- 1. dims must match exactly ----------------------------
        for i, form in enumerate(inputs):
            if form.dims != ref.dims:
                raise StepError(
                    f"Input {i} dims {form.dims} != input 0 dims "
                    f"{ref.dims}. Reorder or rename before concat."
                )
        if axis_name not in ref.dims:
            raise StepError(
                f"Dim '{axis_name}' not in inputs. Available: {ref.dims}"
            )
        axis = ref.axis(axis_name)

        # --- 2. align or keep positional ---------------------------
        if align_cfg:
            subsets = self._align(inputs, input_names, align_cfg, axis_name)
        else:
            subsets = [f.data for f in inputs]

        # --- 3. collapse key columns if requested ------------------
        key_positions: list[int] | None = None
        if merged_label is not None:
            if not align_cfg:
                raise StepError(
                    "concat: 'label' requires an 'align' block"
                )
            key_map = align_cfg["key"]
            key_positions = []
            for name, form in zip(input_names, inputs):
                key_name = key_map.get(name)
                if key_name is None:
                    raise StepError(
                        f"concat: align.key missing input '{name}'"
                    )
                if key_name not in form.labels.get(axis_name, {}):
                    raise StepError(
                        f"concat: label '{key_name}' not found on axis "
                        f"'{axis_name}' of input '{name}'. Available: "
                        f"{sorted(form.labels.get(axis_name, {}))}"
                    )
                key_positions.append(form.labels[axis_name][key_name])

            trimmed = []
            for i, sub in enumerate(subsets):
                if i == 0:
                    trimmed.append(sub)
                else:
                    kp = key_positions[i]
                    keep = [j for j in range(sub.shape[axis]) if j != kp]
                    idx = [slice(None)] * sub.ndim
                    idx[axis] = keep
                    trimmed.append(sub[tuple(idx)])
            subsets = trimmed

        merged = np.concatenate(subsets, axis=axis)

        # --- 4. merge labels ---------------------------------------
        out_labels: dict[str, dict[str, int]] = {}

        # 4a. non-axis dims: intersect labels
        for dim_name in ref.dims:
            if dim_name == axis_name:
                continue
            if dim_name not in ref.labels:
                continue
            order = list(ref.labels[dim_name].keys())
            common = set(order)
            for f in inputs:
                common &= set(f.labels.get(dim_name, {}).keys())
            kept = [l for l in order if l in common]
            if kept:
                out_labels[dim_name] = {l: i for i, l in enumerate(kept)}

        # 4b. axis dim: cumulative offsets, key collapse applied
        axis_labels: dict[str, int] = {}
        offset = 0
        for i, (form, sub) in enumerate(zip(inputs, subsets)):
            mapping = form.labels.get(axis_name, {})
            kp = key_positions[i] if key_positions is not None else None

            if kp is not None and i != 0:
                new_pos = {}
                j = 0
                for orig in range(form.data.shape[axis]):
                    if orig == kp:
                        continue
                    new_pos[orig] = j
                    j += 1
            else:
                new_pos = {orig: orig for orig in range(form.data.shape[axis])}

            for lab, pos in mapping.items():
                if kp is not None and pos == kp:
                    if i == 0:
                        final_lab = merged_label
                    else:
                        continue
                else:
                    final_lab = lab

                if final_lab in axis_labels:
                    raise StepError(
                        f"Duplicate label '{final_lab}' on axis "
                        f"'{axis_name}' after concat. Rename before concat."
                    )
                axis_labels[final_lab] = offset + new_pos[pos]
            offset += sub.shape[axis]

        if axis_labels:
            out_labels[axis_name] = axis_labels

        ctx[out_name] = Form(
            data=merged.astype(np.float32),
            dims=list(ref.dims),
            labels=out_labels,
            info={"missing_code": np.nan, "source_format": "derived"},
        )

        print(
            f"[concat] {len(inputs)} forms along '{axis_name}' "
            f"-> {out_name}, shape={merged.shape}"
        )

    # ------------------------------------------------------------------ #
    # Alignment
    # ------------------------------------------------------------------ #

    @staticmethod
    def _align(inputs, input_names, align_cfg, axis_name):
        align_dim = align_cfg["dim"]
        key_map = align_cfg["key"]

        if align_dim == axis_name:
            raise StepError(
                f"align.dim '{align_dim}' cannot equal axis '{axis_name}'"
            )
        if align_dim not in inputs[0].dims:
            raise StepError(f"align.dim '{align_dim}' not in inputs")

        keys = []
        for name, form in zip(input_names, inputs):
            label = key_map.get(name)
            if label is None:
                raise StepError(
                    f"concat: align.key missing input '{name}'"
                )
            keys.append(_extract_key_vector(form, align_dim, label))

        if any(k.ndim != 1 for k in keys):
            raise StepError(
                "concat: alignment requires the key to be a 1-d vector."
            )

        ref_keys = keys[0]
        common = set(ref_keys.tolist())
        for k in keys[1:]:
            common &= set(k.tolist())
        if not common:
            raise StepError(f"No common keys on dim '{align_dim}'")
        order = [v for v in ref_keys.tolist() if v in common]

        align_axis = inputs[0].axis(align_dim)
        subsets = []
        for form, kv in zip(inputs, keys):
            pos_of = {v: i for i, v in enumerate(kv.tolist())}
            positions = [pos_of[v] for v in order]
            index = [slice(None)] * form.data.ndim
            index[align_axis] = positions
            subsets.append(form.data[tuple(index)])
        return subsets


def _extract_key_vector(form: Form, align_dim: str, label: str) -> np.ndarray:
    """Return the values of ``label`` along the non-align axis."""
    for dim_name, mapping in form.labels.items():
        if dim_name == align_dim:
            continue
        if label in mapping:
            pos = mapping[label]
            axis = form.axis(dim_name)
            index = [slice(None)] * form.data.ndim
            index[axis] = pos
            return form.data[tuple(index)]
    raise StepError(
        f"Label '{label}' not found outside dim '{align_dim}' "
        f"in form with dims {form.dims}"
    )