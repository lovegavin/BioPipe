# mardia_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/mardia_test.py`](../../../src/task/step/steps/mardia_test.py)
- Tests: [`tests/test_extension36.py`](../../../tests/test_extension36.py), [`tests/test_r_oracles28.py`](../../../tests/test_r_oracles28.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
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
Mardia's multivariate normality tests.

    Matches ``psych::mardia``: with centered data ``X`` and covariance
    ``S`` (n-1 denominator), ``D = X S^-1 X'``,
    ``b1p = sum(D^3)/n^2`` and ``b2p = trace(D^2)/n``. The skewness
    chi-square uses ``n*b1p/6`` or the small-sample correction
    ``n*k*b1p/6``; kurtosis is standardized by
    ``sqrt(n/(8*p*(p+2)))``.

--- module documentation ---

Mardia multivariate skewness and kurtosis tests.
```

## Minimal YAML skeleton

```yaml
- name: mardia_test
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/mardia_test.md` and regenerate.
