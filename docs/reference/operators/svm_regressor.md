# svm_regressor

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/svm_regressor.py`](../../../src/task/step/steps/svm_regressor.py)
- Tests: [`tasks/ml_regression_route_demo/test_ml_regression.py`](../../../tasks/ml_regression_route_demo/test_ml_regression.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `label_dim` | 标签维度 | string | label |  |  |  | basic |
| `target_label` | 目标字段 | string |  |  |  | yes | basic |
| `test_size` | 测试集比例 | number | 0.25 | 0.05 | 0.5 |  | advanced |
| `cv_folds` | 交叉验证折数 | integer | 5 | 2 |  |  | advanced |
| `random_state` | 随机种子 | integer | 0 |  |  |  | advanced |
| `scale` | 标准化 | boolean | True |  |  |  | basic |
| `output` | 输出名称 | string |  |  |  |  | basic |
| `C` | 正则强度 C | number | 1.0 |  |  |  | advanced |
| `epsilon` | epsilon | number | 0.1 |  |  |  | advanced |

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
  },
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
        "param": "label_dim",
        "default": "label"
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
Abstract step.

Subclasses declare:

* ``name`` — matched against the manifest's ``name`` field.
* ``inputs_arity`` — number of input forms, or ``"*"`` for any.
* ``outputs`` — context keys the step registers on exit.

And implement ``run``. They may also implement ``export`` to
return a JSON-serializable dict of the step's full results.

--- module documentation ---

Linear epsilon-SVR regressor.
```

## Minimal YAML skeleton

```yaml
- name: svm_regressor
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    label_dim: <string>
    target_label: <string>
    test_size: <number>
    cv_folds: <integer>
    random_state: <integer>
    scale: <boolean>
    output: <string>
    C: <number>
    epsilon: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/svm_regressor.md` and regenerate.
