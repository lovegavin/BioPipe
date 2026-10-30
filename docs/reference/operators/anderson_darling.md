# anderson_darling

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/anderson_darling.py`](../../../src/task/step/steps/anderson_darling.py)
- Tests: [`tests/test_extension37.py`](../../../tests/test_extension37.py), [`tests/test_r_oracles29.py`](../../../tests/test_r_oracles29.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
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
Anderson-Darling composite normality test.

    Uses the mean and sample standard deviation estimated from the data, as
    in ``nortest::ad.test``. The statistic is

    ``A = -n - mean((2i-1) * (log F(z_i) + log(1-F(z_{n+1-i}))))``

    and the p-value uses the adjusted statistic with the piecewise
    approximations from that implementation.

--- module documentation ---

Anderson-Darling normality test with estimated mean and variance.
```

## Minimal YAML skeleton

```yaml
- name: anderson_darling
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/anderson_darling.md` and regenerate.
