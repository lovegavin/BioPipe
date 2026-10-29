# drop

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/drop.py`](../../../src/task/step/steps/drop.py)
- Tests: [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/drop_demo/task.yaml`](../../../tasks/drop_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 移除维度 | string |  |  |  | yes | basic |
| `labels` | 移除的标签 | array |  |  |  | yes | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [
      {
        "dim": {
          "param": "dim",
          "default": null
        },
        "values": {
          "param": "labels",
          "default": null
        }
      }
    ],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "drop"
}
```

## Processing rules (source docstring)

```text
Remove a set of labels from one dimension.

    Params:
        dim    : dimension from which to drop
        labels : list of label names to remove
        output : context key for the result

--- module documentation ---

Drop step: remove named labels from one dimension.
```

## Minimal YAML skeleton

```yaml
- name: drop
  inputs: [<input1>]
  params:
    dim: <string>
    labels: <array>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/drop.md` and regenerate.
