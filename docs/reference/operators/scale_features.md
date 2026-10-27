# scale_features

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/scale_features.py`](../../../src/task/step/steps/scale_features.py)
- Tests: [`tasks/scale_features_demo/test_scale_features.py`](../../../tasks/scale_features_demo/test_scale_features.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/scale_features_demo/task.yaml`](../../../tasks/scale_features_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string | sample |  |  |  | basic |
| `max_value` | 最大值 | number / null | None |  |  |  | advanced |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    },
    "dims": [
      {
        "param": "dim",
        "default": null
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
  "representation": "scaled"
}
```

## Processing rules (source docstring)

```text
Z-score standardise a 2D Form along one axis.

--- module documentation ---

Z-score standardisation along one axis of a 2D numeric Form.

Input: any 2D Form. Missing cells are recognised from
info["missing_code"]; when that code is NaN, non-finite cells count
as missing. Missing cells stay missing in the output.

For every position along the *other* axis, values are rescaled so
that, across ``dim``, they have mean 0 and population standard
deviation 1:

    x' = (x - mean_over_dim) / std_over_dim

Mean and std are computed with NaN-aware aggregation. Positions whose
std is effectively zero are shifted to 0 (the numerator is already
0 for a constant row), not turned into NaN.

When ``max_value`` is given, the rescaled value is clipped to
[-max_value, +max_value] after standardisation.

Output: same dims and labels as the input. ``data`` is replaced;
``representation`` becomes ``"scaled"``; genotype/alphabet semantics
and encoders are cleared because the numeric values no longer mean
what they meant.

Params:
    dim        : axis to standardise *along* (default "sample")
                 e.g. dim="sample" scales each feature across samples
                 dim="feature" scales each sample across features
    max_value  : optional clip on the absolute standardised value
    output     : context key (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: scale_features
  inputs: [<input1>]
  params:
    dim: <string>
    max_value: <number / null>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/scale_features.md` and regenerate.
