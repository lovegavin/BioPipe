# var_model

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/var_model.py`](../../../src/task/step/steps/var_model.py)
- Tests: [`tests/test_extension69.py`](../../../tests/test_extension69.py), [`tests/test_r_oracles60.py`](../../../tests/test_r_oracles60.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `lags` | Lags | integer | 1 | 1 |  |  | basic |
| `trend` | Trend | string; enum=['c', 'n', 'ct'] | c |  |  |  | basic |
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
Estimate a VAR(p) model with a deterministic OLS fit.

--- module documentation ---

Vector autoregression with OLS estimation.
```

## Minimal YAML skeleton

```yaml
- name: var_model
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    lags: <integer>
    trend: <string; enum=['c', 'n', 'ct']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/var_model.md` and regenerate.
