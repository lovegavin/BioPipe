# concat

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/concat.py`](../../../src/task/step/steps/concat.py)
- Tests: [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/concat_demo/task.yaml`](../../../tasks/concat_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml)
- Inputs arity: `*`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `align` | Alignment | object / array |  |  |  |  | advanced |
| `axis` | 合并维度 | string |  |  |  | yes | basic |
| `label` | Merged key label | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "axis",
        "default": null
      }
    ],
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "concat"
}
```

## Processing rules (source docstring)

```text
Concatenate inputs on axis; align other axes by label or a unique key.

--- module documentation ---

Concatenate tensors and their annotations after explicit axis alignment.
```

## Minimal YAML skeleton

```yaml
- name: concat
  inputs: [<input1>]
  params:
    align: <object / array>
    axis: <string>
    label: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（合并）

- 按 `axis` 拼接；其他维按**标签交集**对齐，不是按位置硬拼。输入标签不一致时只会保留共同标签。
- `align` 用于按唯一 key 重排/对齐另一维；key 必须唯一、非缺失，且编码一致。
- 输入必须维度相同（包括 axis）；不同维先 `transpose`/`rename_dim`。
- 输出不会自动去重/改名；重复标签会报错或产生不可预期结果，先检查。
- `_input_names` 是引擎内部键，不是 YAML 参数；写了会被剥离。
