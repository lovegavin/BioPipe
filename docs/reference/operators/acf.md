# acf

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/acf.py`](../../../src/task/step/steps/acf.py)
- Tests: [`tests/test_extension54.py`](../../../tests/test_extension54.py), [`tests/test_r_oracles45.py`](../../../tests/test_r_oracles45.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `lags` | Lags | integer | 10 | 1 |  |  | basic |
| `alpha` | 显著性水平 | number | 0.05 | 0.001 | 0.5 |  | advanced |
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
Autocorrelation function for a univariate series.
```

## Minimal YAML skeleton

```yaml
- name: acf
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    lags: <integer>
    alpha: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/acf.md` and regenerate.
