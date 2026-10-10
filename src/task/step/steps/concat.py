# src/task/step/steps/concat.py
"""Concat step: stack several forms along one dimension.

Every input must carry a label mapping for every dim. Alignment on
non-axis dims uses those labels: the intersection is taken in the
first input's order.

Along the axis dim, labels are concatenated with cumulative offsets.
When ``label`` is given, the key columns collapse into a single
output label of that name.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class ConcatStep(Step):
    """Concatenate several forms along one dimension.

    Params:
        axis   : dimension to concatenate along
        align  : optional ``{dim: name, key: {input: label}}``
        label  : optional name for the merged key column
        output : context key for the result
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
        for i, form in enumerate(inputs):
            if form.dims != ref.dims:
                raise StepError(
                    f"Input {i} dims {form.dims} != input 0 dims "
                    f"{ref.dims}"
                )
        if axis_name not in ref.dims:
            raise StepError(
                f"Dim '{axis_name}' not in inputs. "
                f"Available: {ref.dims}"
            )
        axis = ref.dims.index(axis_name)

        key_positions: list[int] | None = None
        align_dims: dict[str, list] = {}

        if align_cfg:
            align_dim = align_cfg["dim"]
            key_map = align_cfg["key"]
            subsets = _align_by_key(
                inputs, input_names, align_dim, key_map, axis_name
            )

            if merged_label is not None:
                key_positions = []
                for name, form in zip(input_names, inputs):
                    kn = key_map[name]
                    if kn not in form.labels.get(axis_name, {}):
                        raise StepError(
                            f"Key '{kn}' not on dim '{axis_name}' "
                            f"of input '{name}'"
                        )
                    key_positions.append(form.labels[axis_name][kn])

                trimmed = []
                for i, (sub, kp) in enumerate(
                    zip(subsets, key_positions)
                ):
                    if i == 0:
                        trimmed.append(sub)
                    else:
                        keep = [
                            j for j in range(sub.shape[axis])
                            if j != kp
                        ]
                        idx = [slice(None)] * sub.ndim
                        idx[axis] = keep
                        trimmed.append(sub[tuple(idx)])
                subsets = trimmed
        else:
            align_dims, subsets = _align_by_labels(
                ref, inputs, axis_name
            )

        merged = np.concatenate(subsets, axis=axis)

        out_labels: dict[str, dict[str, int]] = {}

        for dim_name in ref.dims:
            if dim_name == axis_name:
                continue
            if dim_name in align_dims:
                out_labels[dim_name] = {
                    l: i for i, l in enumerate(align_dims[dim_name])
                }

        if align_cfg:
            for dim_name in ref.dims:
                if dim_name == axis_name:
                    continue
                if dim_name in out_labels:
                    continue
                out_labels[dim_name] = dict(ref.labels[dim_name])

        axis_labels: dict[str, int] = {}
        offset = 0
        for i, (form, sub) in enumerate(zip(inputs, subsets)):
            kp = key_positions[i] if key_positions is not None else None
            if kp is not None and i != 0:
                remap = {}
                j = 0
                for orig in range(form.data.shape[axis]):
                    if orig == kp:
                        continue
                    remap[orig] = j
                    j += 1
            else:
                remap = {p: p for p in range(form.data.shape[axis])}

            for lab, pos in form.labels.get(axis_name, {}).items():
                if kp is not None and pos == kp:
                    if i == 0:
                        final = merged_label
                    else:
                        continue
                else:
                    final = lab
                if final in axis_labels:
                    raise StepError(
                        f"Duplicate label '{final}' on axis "
                        f"'{axis_name}'"
                    )
                axis_labels[final] = offset + remap[pos]
            offset += sub.shape[axis]

        if axis_labels:
            out_labels[axis_name] = axis_labels

        ctx[out_name] = Form(
            data=merged.astype(np.float32),
            dims=list(ref.dims),
            labels=out_labels,
            info=dict(ref.info),
        )

        self._export_data = {
            "axis": axis_name,
            "n_inputs": len(inputs),
            "input_names": list(input_names),
            "input_shapes": [list(f.data.shape) for f in inputs],
            "output_shape": list(merged.shape),
            "output_dims": list(ref.dims),
            "output_label_counts": {
                dim: len(mapping)
                for dim, mapping in out_labels.items()
            },
        }

        print(
            f"[concat] {len(inputs)} forms along '{axis_name}' "
            f"-> {out_name}, shape={merged.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _align_by_key(inputs, input_names, align_dim, key_map, axis_name):
    keys = []
    for name, form in zip(input_names, inputs):
        kn = key_map.get(name)
        if kn is None:
            raise StepError(f"align.key missing input '{name}'")
        if align_dim not in form.dims:
            raise StepError(f"Input '{name}' has no dim '{align_dim}'")
        if kn not in form.labels.get(axis_name, {}):
            raise StepError(
                f"Key '{kn}' not on axis '{axis_name}' of input '{name}'"
            )
        axis_pos = form.labels[axis_name][kn]
        idx = [slice(None)] * form.data.ndim
        idx[form.dims.index(axis_name)] = axis_pos
        keys.append(form.data[tuple(idx)])

    ref_keys = keys[0]
    common = set(ref_keys.tolist())
    for k in keys[1:]:
        common &= set(k.tolist())
    if not common:
        raise StepError(f"No common keys on '{align_dim}'")
    order = [v for v in ref_keys.tolist() if v in common]

    align_axis = inputs[0].dims.index(align_dim)
    subsets = []
    for form, kv in zip(inputs, keys):
        pos_of = {v: i for i, v in enumerate(kv.tolist())}
        positions = [pos_of[v] for v in order]
        idx = [slice(None)] * form.data.ndim
        idx[align_axis] = positions
        subsets.append(form.data[tuple(idx)])
    return subsets


def _align_by_labels(ref, inputs, axis_name):
    align_dims: dict[str, list] = {}
    for dim_name in ref.dims:
        if dim_name == axis_name:
            continue
        order = list(ref.labels[dim_name].keys())
        common = set(order)
        for f in inputs:
            common &= set(f.labels[dim_name].keys())
        kept = [l for l in order if l in common]
        if not kept:
            raise StepError(
                f"concat: no common labels on dim '{dim_name}'"
            )
        align_dims[dim_name] = kept

    subsets = []
    for form in inputs:
        idx = [slice(None)] * form.data.ndim
        for dim_name, labels in align_dims.items():
            a = form.dims.index(dim_name)
            idx[a] = [form.labels[dim_name][l] for l in labels]
        subsets.append(form.data[tuple(idx)])
    return align_dims, subsets