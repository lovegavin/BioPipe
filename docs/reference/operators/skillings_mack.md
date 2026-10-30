# skillings_mack

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/skillings_mack.py`](../../../src/task/step/steps/skillings_mack.py)
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
Skillings-Mack test for an arbitrary incomplete block design.

    Blocks may contain different numbers of treatments and cells may be
    missing. The covariance matrix is built from the pattern of blocks in
    which each pair of treatments is observed. The observation graph must
    connect all treatments; otherwise the statistic is not identified.

--- module documentation ---

Skillings-Mack rank test for incomplete block designs.
```

## Minimal YAML skeleton

```yaml
- name: skillings_mack
  inputs: [<input1>]
  params:
    block_dim: <string>
    treatment_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/skillings_mack.md` and regenerate.
