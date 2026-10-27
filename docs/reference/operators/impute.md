# impute

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/impute.py`](../../../src/task/step/steps/impute.py)
- Tests: [`tasks/ml_classification_route_demo/test_ml_classification.py`](../../../tasks/ml_classification_route_demo/test_ml_classification.py), [`tasks/ml_regression_route_demo/test_ml_regression.py`](../../../tasks/ml_regression_route_demo/test_ml_regression.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_ml_classification.py`](../../../tasks/verify_ml_classification.py), [`tasks/verify_ml_regression.py`](../../../tasks/verify_ml_regression.py)
- Demo tasks: [`tasks/impute_demo/task.yaml`](../../../tasks/impute_demo/task.yaml), [`tasks/ml_classification_route_demo/task.yaml`](../../../tasks/ml_classification_route_demo/task.yaml), [`tasks/ml_regression_route_demo/task.yaml`](../../../tasks/ml_regression_route_demo/task.yaml), [`tasks/normalize_quantile_demo/task.yaml`](../../../tasks/normalize_quantile_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `method` | 方法 | any; enum=['min', 'median', 'mean'] |  |  |  | yes | basic |
| `min_scale` | 最小值倍率 | number | 1.0 | 0 |  |  | advanced |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "transform",
  "representation": "impute"
}
```

## Processing rules (source docstring)

```text
Fill missing values in a form.

--- module documentation ---

Impute missing values in a form.

Fills missing cells using a simple strategy. Common in proteomics
and metabolomics, where missing values are frequent (low-abundance
features fall below the detection limit).

Methods
-------
    min     replace every missing cell with (global minimum *
            ``min_scale``). This is the Perseus "replace by minimum"
            strategy.
    median  replace each missing cell with the median of its feature,
            computed over all other axes.
    mean    replace each missing cell with the mean of its feature,
            computed over all other axes.

The ``dim`` parameter names the feature axis. For ``median`` and
``mean``, the statistic is computed over every axis except ``dim``.
For ``min``, the statistic is the global minimum over the whole
matrix.

The operator works on any dimensionality >= 1. ``median`` and
``mean`` require at least one axis besides ``dim`` to aggregate
over; for 1D input, use ``method="min"``.

Missing cells are identified via ``info["missing_code"]`` when set
and finite, otherwise via NaN. The output has the same dims, labels,
info and axis_info as the input; only ``data`` is replaced.

Params:
    method     : "min" | "median" | "mean" (required)
    dim        : feature dim (required)
    min_scale  : multiplier for the min method (default 1.0)
    output     : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: impute
  inputs: [<input1>]
  params:
    dim: <string>
    method: <any; enum=['min', 'median', 'mean']>
    min_scale: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/impute.md` and regenerate.
