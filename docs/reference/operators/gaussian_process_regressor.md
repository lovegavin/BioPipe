# gaussian_process_regressor

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/gaussian_process_regressor.py`](../../../src/task/step/steps/gaussian_process_regressor.py)
- Tests: [`tests/test_gaussian_process_regressor.py`](../../../tests/test_gaussian_process_regressor.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `response_label` | 响应列 | string |  |  |  | yes | basic |
| `predictors` | 预测变量列 | array |  |  |  | yes | basic |
| `length_scale` | RBF 长度尺度 | any | 1.0 |  |  |  | basic |
| `alpha` | 观测噪声方差 | number | 1e-06 | 0 |  |  | advanced |
| `normalize_y` | 标准化响应 | boolean | True |  |  |  | basic |
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
Fit a Gaussian-process regressor with a fixed RBF kernel.

    The kernel length scale and noise level are fixed by the user; no
    marginal-likelihood optimisation is performed.  This keeps fits
    deterministic and makes the posterior mean/variance reproducible from
    the closed-form GP equations.

--- module documentation ---

Gaussian-process regression with a fixed RBF kernel.
```

## Minimal YAML skeleton

```yaml
- name: gaussian_process_regressor
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    response_label: <string>
    predictors: <array>
    length_scale: <any>
    alpha: <number>
    normalize_y: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/gaussian_process_regressor.md` and regenerate.
