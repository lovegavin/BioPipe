# calibration_curve

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/calibration_curve.py`](../../../src/task/step/steps/calibration_curve.py)
- Tests: [`tests/test_extension46.py`](../../../tests/test_extension46.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `true_label` | 真实标签列 | string |  |  |  | yes | basic |
| `prob_label` | 预测概率列 | string |  |  |  | yes | basic |
| `n_bins` | N Bins | integer | 10 | 2 | 50 |  | basic |
| `strategy` | Strategy | string; enum=['uniform', 'quantile'] | uniform |  |  |  | basic |
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
Reliability curve with uniform or quantile probability bins.

    Bins with no observations are omitted. ``observed_fraction`` is the
    fraction of positive labels in the bin and ``mean_predicted`` is the mean
    predicted probability, matching ``sklearn.calibration.calibration_curve``
    for the uniform strategy.

--- module documentation ---

Binned calibration curve for binary predictions.
```

## Minimal YAML skeleton

```yaml
- name: calibration_curve
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    true_label: <string>
    prob_label: <string>
    n_bins: <integer>
    strategy: <string; enum=['uniform', 'quantile']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/calibration_curve.md` and regenerate.
