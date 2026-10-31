# lowess

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/lowess.py`](../../../src/task/step/steps/lowess.py)
- Tests: [`tests/test_extension80.py`](../../../tests/test_extension80.py), [`tests/test_r_oracles70.py`](../../../tests/test_r_oracles70.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `x_label` | 自变量列 | string |  |  |  | yes | basic |
| `y_label` | 因变量列 | string |  |  |  | yes | basic |
| `frac` | 平滑窗口比例 | number | 0.6666666666666666 |  | 1 |  | basic |
| `iterations` | 稳健迭代次数 | integer | 3 | 0 | 10 |  | basic |
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
Cleveland's LOWESS smoother with a fixed span and robust iterations.

    The implementation delegates the local regressions to
    ``statsmodels.nonparametric.smoothers_lowess.lowess``, which matches R's
    ``stats::lowess`` for the same span and iteration count.

--- module documentation ---

Locally weighted scatterplot smoothing (LOWESS).
```

## Minimal YAML skeleton

```yaml
- name: lowess
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    x_label: <string>
    y_label: <string>
    frac: <number>
    iterations: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/lowess.md` and regenerate.
