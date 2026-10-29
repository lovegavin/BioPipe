# sgd_classifier

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/sgd_classifier.py`](../../../src/task/step/steps/sgd_classifier.py)
- Tests: [`tests/test_extension3.py`](../../../tests/test_extension3.py)
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
| `valid_labels` | 有效标签 | array |  |  |  |  | advanced |
| `loss` | Loss | string; enum=['hinge', 'log_loss', 'modified_huber'] | hinge |  |  |  | basic |
| `penalty` | 惩罚项 | string; enum=['l2', 'l1', 'elasticnet'] | l2 |  |  |  | advanced |
| `alpha` | 显著性水平 | number | 0.0001 |  |  |  | advanced |
| `max_iter` | Max Iter | integer | 1000 | 1 |  |  | basic |

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
Linear classifier trained with stochastic gradient descent.
```

## Minimal YAML skeleton

```yaml
- name: sgd_classifier
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
    valid_labels: <array>
    loss: <string; enum=['hinge', 'log_loss', 'modified_huber']>
    penalty: <string; enum=['l2', 'l1', 'elasticnet']>
    alpha: <number>
    max_iter: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/sgd_classifier.md` and regenerate.
