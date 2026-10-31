# vecm

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/vecm.py`](../../../src/task/step/steps/vecm.py)
- Tests: [`tests/test_r_oracles77.py`](../../../tests/test_r_oracles77.py), [`tests/test_vecm.py`](../../../tests/test_vecm.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `coint_rank` | 协整秩 | integer | 1 | 1 |  |  | basic |
| `k_ar_diff` | 差分滞后阶数 | integer | 1 | 1 |  |  | basic |
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
        "param": "sample_dim",
        "default": "sample"
      },
      {
        "param": "feature_dim",
        "default": "feature"
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
Estimate a VECM and expose the Johansen trace/eigen diagnostics.

    The Johansen eigenvalues and trace statistics use the constant-in-model
    convention matching R ``urca::ca.jo(ecdet = "none")``.  Coefficients are
    reported on the same normalization as R: the first variable of each
    cointegrating relation is fixed to one.

--- module documentation ---

Vector error correction model (VECM).
```

## Minimal YAML skeleton

```yaml
- name: vecm
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    coint_rank: <integer>
    k_ar_diff: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/vecm.md` and regenerate.
