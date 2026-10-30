# cox_stuart_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cox_stuart_test.py`](../../../src/task/step/steps/cox_stuart_test.py)
- Tests: [`tests/test_extension37.py`](../../../tests/test_extension37.py), [`tests/test_r_oracles29.py`](../../../tests/test_r_oracles29.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `alternative` | 备择假设 | string; enum=['two-sided', 'increasing', 'decreasing'] | two-sided |  |  |  | basic |
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
Cox-Stuart sign test for a monotone trend.

    The series is split into two halves after dropping the middle value of an
    odd-length series. Discordant pairs (second value greater than the first)
    are counted and compared with ``Binomial(n_pairs, 0.5)``; tied pairs are
    excluded from the binomial sample size, matching
    ``randtests::cox.stuart.test``.

--- module documentation ---

Cox-Stuart test for monotone trend.
```

## Minimal YAML skeleton

```yaml
- name: cox_stuart_test
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    alternative: <string; enum=['two-sided', 'increasing', 'decreasing']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cox_stuart_test.md` and regenerate.
