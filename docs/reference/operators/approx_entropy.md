# approx_entropy

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/approx_entropy.py`](../../../src/task/step/steps/approx_entropy.py)
- Tests: [`tests/test_extension62.py`](../../../tests/test_extension62.py), [`tests/test_r_oracles53.py`](../../../tests/test_r_oracles53.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `embedding_dim` | Embedding Dim | integer | 2 | 1 | 5 |  | basic |
| `radius` | Radius | number |  |  |  |  | basic |
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
Approximate entropy for a univariate series.

    ``ApEn(m, r) = phi(m) - phi(m+1)`` where ``phi(m)`` is the mean log
    fraction of embedded vectors within Chebyshev distance ``r``
    (including the vector itself).  With the defaults this is the same
    quantity reported by R ``pracma::approx_entropy``.

--- module documentation ---

Approximate entropy (ApEn), matching R pracma::approx_entropy.
```

## Minimal YAML skeleton

```yaml
- name: approx_entropy
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    embedding_dim: <integer>
    radius: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/approx_entropy.md` and regenerate.
