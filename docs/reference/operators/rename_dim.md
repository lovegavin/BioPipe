# rename_dim

> Reviewed reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/rename_dim.py`](../../../src/task/step/steps/rename_dim.py)
- Tests: [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/rename_dim_demo/task.yaml`](../../../tasks/rename_dim_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `from` | 原维度 | string |  |  |  | yes | basic |
| `to` | 新维度 | string |  |  |  | yes | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "from",
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
  "mode": "rename"
}
```

## Processing rules (source docstring)

```text
Rename a single dimension.

Params:
    from   : current dim name
    to     : new dim name
    output : context key for the result

--- module documentation ---

Rename one dimension of a form.
```

## Minimal YAML skeleton

```yaml
- name: rename_dim
  inputs: [<input1>]
  params:
    from: <string>
    to: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Curated notes

## 审校补充（重命名维度）

- 只改维度名，不改 data/labels 的值；`from` 必须存在，`to` 不能与现有维度重名。
- 用于把通用 `feature/sample` 改成领域名（gene/cell、protein/sample），便于后续算子匹配。
- 不代表数据语义变化；如果值含义也变了，需要同时 `transpose`/转换算子。
- 下游 `dims`/labels 参数要用新名字；旧名字会报错。
