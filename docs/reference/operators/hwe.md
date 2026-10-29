# hwe

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/hwe.py`](../../../src/task/step/steps/hwe.py)
- Tests: [`tasks/verify_genetics_operators.py`](../../../tasks/verify_genetics_operators.py)
- Demo tasks: [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/hwe_demo/task.yaml`](../../../tasks/hwe_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 变异维度 | string |  |  |  | yes | basic |
| `threshold` | 最低 P 值 | number | 1e-06 | 0 | 1 |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      },
      "ploidy": {
        "type": "integer",
        "const": 2
      },
      "representation": {
        "type": "string",
        "const": "hard_call"
      }
    },
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": [],
    "values": "hard_call"
  }
]
```

## Output contract

```json
{
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Filter positions along one dimension by HWE p-value.

    Params:
        dim       : dimension to test along
        threshold : minimum allowed p-value
        output    : context key for the result

--- module documentation ---

Hardy-Weinberg equilibrium filter.

Reference
---------
Wigginton JE, Cutler DJ, Abecasis GR (2005).
A note on exact tests of Hardy-Weinberg equilibrium.
Am J Hum Genet 76(5):887-93.
```

## Minimal YAML skeleton

```yaml
- name: hwe
  inputs: [<input1>]
  params:
    dim: <string>
    threshold: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/hwe.md` and regenerate.
