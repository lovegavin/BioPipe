# dca

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/dca.py`](../../../src/task/step/steps/dca.py)
- Tests: [`tests/test_extension80.py`](../../../tests/test_extension80.py), [`tests/test_r_oracles70.py`](../../../tests/test_r_oracles70.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `outcome_label` | 二分类结局列 | string |  |  |  | yes | basic |
| `probability_label` | 预测概率列 | string |  |  |  | yes | basic |
| `thresholds` | 阈值列表（可选） | array |  |  |  |  | basic |
| `threshold_start` | Threshold Start | number | 0.01 | 0 | 1 |  | basic |
| `threshold_stop` | Threshold Stop | number | 0.99 | 0 | 1 |  | basic |
| `threshold_step` | Threshold Step | number | 0.01 |  | 1 |  | basic |
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
Net benefit of a binary prediction rule across probability thresholds.

    The net benefit follows the standard decision-curve formulation
    ``TP/n - FP/n * pt/(1-pt)``. The treat-all and treat-none reference
    strategies are reported on the same threshold grid.

--- module documentation ---

Decision curve analysis for binary prediction models.
```

## Minimal YAML skeleton

```yaml
- name: dca
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    outcome_label: <string>
    probability_label: <string>
    thresholds: <array>
    threshold_start: <number>
    threshold_stop: <number>
    threshold_step: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/dca.md` and regenerate.
