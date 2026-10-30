# durbin_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/durbin_test.py`](../../../src/task/step/steps/durbin_test.py)
- Tests: [`tests/test_extension42.py`](../../../tests/test_extension42.py), [`tests/test_r_oracles33.py`](../../../tests/test_r_oracles33.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `block_dim` | Block Dim | string | block |  |  |  | basic |
| `treatment_dim` | Treatment Dim | string | treatment |  |  |  | basic |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "block_dim",
        "default": "block"
      },
      {
        "param": "treatment_dim",
        "default": "treatment"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  }
]
```

## Output contract

```json
{
  "mode": "declare",
  "schema": {
    "ndim": 2,
    "numeric": true,
    "info_open": true,
    "axis_info_open": true
  }
}
```

## Processing rules (source docstring)

```text
Durbin's rank sum test for a balanced incomplete block design.

    Each block contains the same number ``k`` of the ``t`` treatments, every
    treatment occurs in the same number ``r`` of blocks, and the design is
    incomplete (``k < t``). Missing cells are represented by NaN.

--- module documentation ---

Durbin rank test for a balanced incomplete block design.
```

## Minimal YAML skeleton

```yaml
- name: durbin_test
  inputs: [<input1>]
  params:
    block_dim: <string>
    treatment_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/durbin_test.md` and regenerate.
