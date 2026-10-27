# attach_info

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/attach_info.py`](../../../src/task/step/steps/attach_info.py)
- Tests: [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py)
- Demo tasks: [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `fields` | 注释字段 | array |  |  |  | yes | basic |
| `target_dim` | 目标维度 | string |  |  |  | yes | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "target_dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": []
  },
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [],
    "labels": [],
    "parallel": [
      {
        "fields": {
          "param": "fields",
          "default": null
        }
      }
    ]
  }
]
```

## Output contract

```json
{
  "mode": "attach"
}
```

## Processing rules (source docstring)

```text
Attach source info arrays to a target dimension.

Inputs:
    target : form to attach onto
    source : form whose info holds the arrays

Params:
    fields     : list of info keys to attach
    target_dim : dimension of the target to align against
    output     : context key for the result

--- module documentation ---

Attach axis-parallel info arrays from a source form onto a target.

The source declares which info keys are parallel to which axis via
``axis_info``. This step reads those arrays, aligns them to the
target axis by label, and stores the result as target info entries
declared parallel to the target dim.

Data is never modified.
```

## Minimal YAML skeleton

```yaml
- name: attach_info
  inputs: [<input1>, <input2>]
  params:
    fields: <array>
    target_dim: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/attach_info.md` and regenerate.
