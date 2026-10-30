# remove_batch_effect

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/remove_batch_effect.py`](../../../src/task/step/steps/remove_batch_effect.py)
- Tests: [`tests/test_extension12.py`](../../../tests/test_extension12.py), [`tests/test_r_oracles4.py`](../../../tests/test_r_oracles4.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `batch_label` | Batch Label | string |  |  |  | yes | basic |
| `covariates` | 协变量 | array | [] |  |  |  | basic |
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
        "param": "feature_dim",
        "default": "feature"
      },
      {
        "param": "sample_dim",
        "default": "sample"
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
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_any": [
      {
        "param": "batch_label",
        "default": null
      }
    ]
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
    "info_open": false,
    "axis_info_open": false,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    }
  }
}
```

## Processing rules (source docstring)

```text
Remove batch effects with a linear model (limma-style).

The operator fits one linear model per feature with an intercept, batch
dummy variables and optional covariates. Batch coefficients are then
subtracted from the expression matrix; the intercept and covariate
effects are retained. This matches ``limma::removeBatchEffect`` for
additive batch effects without batch-covariate interactions.
```

## Minimal YAML skeleton

```yaml
- name: remove_batch_effect
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    batch_label: <string>
    covariates: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/remove_batch_effect.md` and regenerate.
