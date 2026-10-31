# arima

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/arima.py`](../../../src/task/step/steps/arima.py)
- Tests: [`tests/test_extension79.py`](../../../tests/test_extension79.py), [`tests/test_r_oracles69.py`](../../../tests/test_r_oracles69.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `p` | P | integer | 1 | 0 | 4 |  | basic |
| `d` | D | integer | 0 | 0 | 2 |  | basic |
| `q` | Q | integer | 0 | 0 | 4 |  | basic |
| `trend` | Trend | string; enum=['c', 'n'] | c |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
| `maxiter` | Maxiter | integer | 200 | 10 |  |  | basic |
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
Fit a non-seasonal ARIMA(p, d, q) model by maximum likelihood.

--- module documentation ---

ARIMA time-series model.
```

## Minimal YAML skeleton

```yaml
- name: arima
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    p: <integer>
    d: <integer>
    q: <integer>
    trend: <string; enum=['c', 'n']>
    confidence: <number>
    maxiter: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/arima.md` and regenerate.
