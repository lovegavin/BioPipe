# meta_regression

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/meta_regression.py`](../../../src/task/step/steps/meta_regression.py)
- Tests: [`tests/test_extension72.py`](../../../tests/test_extension72.py), [`tests/test_r_oracles63.py`](../../../tests/test_r_oracles63.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `study_dim` | Study Dim | string | study |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `effect_label` | Effect Label | string |  |  |  | yes | basic |
| `variance_label` | Variance Label | string |  |  |  | yes | basic |
| `moderators` | Moderators | array |  |  |  | yes | basic |
| `categorical` | 分类协变量 | array | [] |  |  |  | basic |
| `method` | 方法 | string; enum=['fixed', 'random'] | random |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
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
        "param": "study_dim",
        "default": "study"
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
Inverse-variance meta-regression of study-level effect sizes.

The input is one ``[study, feature]`` table containing an effect estimate,
its sampling variance, and one or more study-level moderators.  An
intercept and the requested moderators are fitted by weighted least
squares.  ``fixed`` uses inverse-variance weights; ``random`` adds a
DerSimonian-Laird between-study variance to each weight.
```

## Minimal YAML skeleton

```yaml
- name: meta_regression
  inputs: [<input1>]
  params:
    study_dim: <string>
    feature_dim: <string>
    effect_label: <string>
    variance_label: <string>
    moderators: <array>
    categorical: <array>
    method: <string; enum=['fixed', 'random']>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/meta_regression.md` and regenerate.
