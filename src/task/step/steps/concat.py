"""Concatenate tensors and their annotations after explicit axis alignment."""
import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.core.forms.metadata import concat_metadata, equal_metadata
from src.task.step.base import Step


class ConcatStep(Step):
    """Concatenate inputs on axis; align other axes by label or a unique key."""
    parameters_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
     'type': 'object',
     'properties': {'axis': {'title': '合并维度', 'type': 'string', 'x-ui-default': 'feature'},
                    'align': {'title': 'Alignment', 'type': ['object', 'array']},
                    'label': {'title': 'Merged key label', 'type': 'string'}},
     'additionalProperties': True,
     'required': ['axis']}
    title = '合并数据'
    category = '数据整理'
    icon = 'Unite'
    description = '按指定维度连接多个输入，输入端口顺序决定合并顺序。'
    name = "concat"
    inputs_arity = "*"
    outputs = []
    input_contracts = [port(dims=[param("axis")])]
    output_contract = {"mode": "concat"}
    output_parameter = "output"

    def run(self, ctx, inputs):
        if len(inputs) < 2:
            raise StepError("concat needs at least two inputs")
        axis = ctx.step_params["axis"]
        out_name = ctx.step_params["output"]
        align = ctx.step_params.get("align")
        merged_label = ctx.step_params.get("label")
        names = ctx.step_params.get("_input_names", [])
        ref = inputs[0]
        if axis not in ref.dims or any(f.dims != ref.dims for f in inputs):
            raise StepError("concat: inputs must have identical dimensions including axis")
        aligned = list(inputs)
        key_labels = []
        if align:
            dim = align["dim"]
            if ref.data.ndim != 2 or dim not in ref.dims or dim == axis:
                raise StepError("concat: key alignment requires a separate axis on a 2D tensor")
            keys, encoders = [], []
            for name, form in zip(names, inputs):
                label = align["key"].get(name)
                if label not in form.labels[axis]:
                    raise StepError(f"concat: missing key label for {name}")
                key_labels.append(label)
                values = np.take(form.data, form.labels[axis][label], axis=form.axis(axis)).tolist()
                if len(set(values)) != len(values) or not np.isfinite(values).all():
                    raise StepError("concat: alignment keys must be unique and nonmissing")
                keys.append(values)
                encoders.append(form.info.get("encoders", {}).get(axis, {}).get(label))
            if len(keys) != len(inputs):
                raise StepError("concat: input names required for key alignment")
            if any(not equal_metadata(encoders[0], encoder) for encoder in encoders[1:]):
                raise StepError("concat: alignment key encodings differ")
            common = set(keys[0]).intersection(*(set(values) for values in keys[1:]))
            order = [value for value in keys[0] if value in common]
            if not order:
                raise StepError("concat: no common alignment keys")
            for i, (form, values) in enumerate(zip(inputs, keys)):
                positions = {key: pos for pos, key in enumerate(values)}
                aligned[i] = form.subset_axis(dim, [positions[key] for key in order])
                aligned[i].labels[dim] = dict(aligned[0].labels[dim])
        else:
            for dim in ref.dims:
                if dim == axis:
                    continue
                order = [label for label, _ in sorted(ref.labels[dim].items(), key=lambda item: item[1])
                         if all(label in f.labels[dim] for f in inputs)]
                if not order:
                    raise StepError(f"concat: no common labels on {dim}")
                for i, form in enumerate(aligned):
                    # Independent takes avoid advanced indexing's diagonal selection.
                    aligned[i] = form.subset_axis(dim, [form.labels[dim][label] for label in order])
        if align and merged_label is not None:
            for i, form in enumerate(aligned):
                key = key_labels[i]
                pos = form.labels[axis][key]
                if i:
                    aligned[i] = form.subset_axis(axis, [j for j in range(form.data.shape[form.axis(axis)]) if j != pos])
                else:
                    if merged_label != key and merged_label in form.labels[axis]:
                        raise StepError("concat: merged key label already exists")
                    form.labels[axis] = {merged_label if label == key else label: p for label, p in form.labels[axis].items()}
                    fields = form.info.get("encoders", {}).get(axis, {})
                    if key in fields:
                        fields[merged_label] = fields.pop(key)
        labels, offset = {}, 0
        for form in aligned:
            for label, pos in form.labels[axis].items():
                if label in labels:
                    raise StepError(f"concat: duplicate label {label!r} on {axis}")
                labels[label] = offset + pos
            offset += form.data.shape[form.axis(axis)]
        info, axis_info = concat_metadata(aligned, axis)
        merged = np.concatenate([f.data for f in aligned], axis=ref.axis(axis)).astype(np.float32)
        out_labels = {dim: dict(mapping) for dim, mapping in aligned[0].labels.items()}
        out_labels[axis] = labels
        ctx[out_name] = Form(merged, list(ref.dims), out_labels, info, axis_info)
        self._export_data = {"axis": axis, "n_inputs": len(inputs), "input_names": names,
                             "input_shapes": [list(f.data.shape) for f in inputs],
                             "output_shape": list(merged.shape), "output_dims": list(ref.dims),
                             "output_label_counts": {d: len(m) for d, m in out_labels.items()}}
        print(f"[concat] {len(inputs)} forms along '{axis}' -> {out_name}, shape={merged.shape}")

    def export(self, ctx):
        return self._export_data
