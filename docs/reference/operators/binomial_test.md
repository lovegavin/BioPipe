# binomial_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/binomial_test.py`](../../../src/task/step/steps/binomial_test.py)
- Tests: [`tests/test_extension38.py`](../../../tests/test_extension38.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `success_value` | 成功取值 | number | 1.0 |  |  |  | basic |
| `null_probability` | 原假设概率 | number | 0.5 | 0.0 | 1.0 |  | basic |
| `alternative` | 备择假设 | string; enum=['two-sided', 'greater', 'less'] | two-sided |  |  |  | basic |
| `confidence` | 置信水平 | number | 0.95 | 0.0 | 1.0 |  | basic |
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
Exact binomial test of ``k`` successes out of ``n`` trials.

    The p-value is the exact binomial tail (or two-sided sum of tails) and the
    confidence interval is the Clopper-Pearson exact interval, matching
    ``scipy.stats.binomtest``.

--- module documentation ---

Exact binomial test for a single proportion.
```

## Minimal YAML skeleton

```yaml
- name: binomial_test
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    success_value: <number>
    null_probability: <number>
    alternative: <string; enum=['two-sided', 'greater', 'less']>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/binomial_test.md` and regenerate.
