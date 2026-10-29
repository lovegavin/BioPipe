# missing

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/missing.py`](../../../src/task/step/steps/missing.py)
- Tests: [`tasks/bgen_qc_demo/test_bgen_qc.py`](../../../tasks/bgen_qc_demo/test_bgen_qc.py), [`tasks/ml_classification_route_demo/test_ml_classification.py`](../../../tasks/ml_classification_route_demo/test_ml_classification.py), [`tasks/ml_regression_route_demo/test_ml_regression.py`](../../../tasks/ml_regression_route_demo/test_ml_regression.py), [`tasks/verify_bgen_qc.py`](../../../tasks/verify_bgen_qc.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_ml_classification.py`](../../../tasks/verify_ml_classification.py), [`tasks/verify_ml_regression.py`](../../../tasks/verify_ml_regression.py)
- Demo tasks: [`tasks/bgen_qc_demo/task.yaml`](../../../tasks/bgen_qc_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/impute_demo/task.yaml`](../../../tasks/impute_demo/task.yaml), [`tasks/missing_demo/task.yaml`](../../../tasks/missing_demo/task.yaml), [`tasks/ml_classification_route_demo/task.yaml`](../../../tasks/ml_classification_route_demo/task.yaml), [`tasks/ml_regression_route_demo/task.yaml`](../../../tasks/ml_regression_route_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 过滤维度 | string |  |  |  | yes | basic |
| `threshold` | 最大缺失比例 | number | 0.1 | 0 | 1 |  | basic |

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
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Filter positions along one dimension by missing rate.

    Params:
        dim       : dimension to filter on
        threshold : maximum allowed missing rate
        output    : context key for the result (default: step name)

--- module documentation ---

Missingness filter along one dimension.
```

## Minimal YAML skeleton

```yaml
- name: missing
  inputs: [<input1>]
  params:
    dim: <string>
    threshold: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/missing.md` and regenerate.
