# tmm_normalize

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/tmm_normalize.py`](../../../src/task/step/steps/tmm_normalize.py)
- Tests: [`tests/test_extension12.py`](../../../tests/test_extension12.py), [`tests/test_r_oracles4.py`](../../../tests/test_r_oracles4.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `target_sum` | 目标总量 | number | 1000000.0 |  |  |  | basic |
| `logratio_trim` | Logratio Trim | number | 0.3 | 0 |  |  | basic |
| `sum_trim` | Sum Trim | number | 0.05 | 0 |  |  | basic |
| `do_weighting` | Do Weighting | boolean | True |  |  |  | basic |
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
  }
]
```

## Output contract

```json
{
  "mode": "transform",
  "representation": "tmm_normalize"
}
```

## Processing rules (source docstring)

```text
Normalize a count matrix with edgeR-style TMM factors.

--- module documentation ---

Trimmed mean of M-values (TMM) normalization.

This is an independent Python implementation of the TMM method from
edgeR. Counts are scaled by effective library sizes

    effective_library_size = library_size * norm_factor

and converted to counts per ``target_sum``. The implementation follows
edgeR's reference-sample selection, trimmed log-ratio mean and optional
inverse-variance weighting, but is not a wrapper around R.
```

## Minimal YAML skeleton

```yaml
- name: tmm_normalize
  inputs: [<input1>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    target_sum: <number>
    logratio_trim: <number>
    sum_trim: <number>
    do_weighting: <boolean>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/tmm_normalize.md` and regenerate.
