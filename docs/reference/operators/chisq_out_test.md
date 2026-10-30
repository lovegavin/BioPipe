# chisq_out_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/chisq_out_test.py`](../../../src/task/step/steps/chisq_out_test.py)
- Tests: [`tests/test_extension46.py`](../../../tests/test_extension46.py), [`tests/test_r_oracles37.py`](../../../tests/test_r_oracles37.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `variance` | 已知方差（留空用样本方差） | number |  |  |  |  | basic |
| `opposite` | 检验另一端 | boolean | False |  |  |  | basic |
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
Chi-square test for one extreme observation.

    Mirrors ``outliers::chisq.out.test``: the farther of the minimum and
    maximum from the sample mean is tested with
    ``chi2 = (extreme - mean)^2 / variance`` on one degree of freedom.
    ``opposite`` forces the other extreme, as in the R implementation.

--- module documentation ---

Chi-square test for a single outlier in a univariate sample.
```

## Minimal YAML skeleton

```yaml
- name: chisq_out_test
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    variance: <number>
    opposite: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/chisq_out_test.md` and regenerate.
