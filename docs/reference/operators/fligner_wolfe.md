# fligner_wolfe

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/fligner_wolfe.py`](../../../src/task/step/steps/fligner_wolfe.py)
- Tests: [`tests/test_extension49.py`](../../../tests/test_extension49.py), [`tests/test_r_oracles40.py`](../../../tests/test_r_oracles40.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `group_dim` | 分组维度 | string | sample |  |  |  | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `control` | 对照组 | string |  |  |  | yes | basic |
| `group_order` | 分组顺序 | array |  |  |  |  | basic |
| `alternative` | Alternative | string; enum=['greater', 'less'] | greater |  |  |  | basic |
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
      },
      {
        "param": "group_dim",
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
Rank test comparing every treatment group with a control group.

    The implementation follows ``PMCMRplus::flignerWolfeTest`` with
    ``dist = "Normal"``: the control group is placed first, all values are
    ranked globally, and the control-versus-rest Mann-Whitney statistic is
    standardized with the tie-corrected null variance.

--- module documentation ---

Fligner-Wolfe test for a shift against a control group.
```

## Minimal YAML skeleton

```yaml
- name: fligner_wolfe
  inputs: [<input1>, <input2>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    group_dim: <string>
    group_label: <string>
    control: <string>
    group_order: <array>
    alternative: <string; enum=['greater', 'less']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/fligner_wolfe.md` and regenerate.
