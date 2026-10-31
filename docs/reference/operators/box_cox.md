# box_cox

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/box_cox.py`](../../../src/task/step/steps/box_cox.py)
- Tests: [`tests/test_box_cox.py`](../../../tests/test_box_cox.py), [`tests/test_r_oracles75.py`](../../../tests/test_r_oracles75.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `lambdas` | 固定 lambda（标量或按特征映射；省略则逐特征 MLE） | any |  |  |  |  | basic |
| `shift` | 变换前加常数，使取值严格为正 | number | 0.0 | 0.0 |  |  | basic |
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
Box-Cox transform each feature, optionally estimating lambda.

--- module documentation ---

Box-Cox power transformation with optional per-feature MLE.

The transformation is ``(x^lambda - 1) / lambda`` for ``lambda != 0`` and
``log(x)`` for ``lambda == 0``.  Each feature can have its own lambda,
estimated by maximising the profile likelihood (the same criterion used by
R's ``MASS::boxcox``).

Missing cells are preserved.  ``shift`` can be used to make a feature
strictly positive before fitting; the shift is applied before the transform
and recorded in ``info``.
```

## Minimal YAML skeleton

```yaml
- name: box_cox
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    lambdas: <any>
    shift: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/box_cox.md` and regenerate.
