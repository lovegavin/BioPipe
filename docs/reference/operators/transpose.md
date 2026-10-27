# transpose

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/transpose.py`](../../../src/task/step/steps/transpose.py)
- Tests: [`tasks/ml_classification_route_demo/test_ml_classification.py`](../../../tasks/ml_classification_route_demo/test_ml_classification.py), [`tasks/ml_regression_route_demo/test_ml_regression.py`](../../../tasks/ml_regression_route_demo/test_ml_regression.py), [`tasks/verify_ml_classification.py`](../../../tasks/verify_ml_classification.py), [`tasks/verify_ml_regression.py`](../../../tasks/verify_ml_regression.py), [`tasks/verify_transform_operators.py`](../../../tasks/verify_transform_operators.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/aggregate_demo/task.yaml`](../../../tasks/aggregate_demo/task.yaml), [`tasks/barplot_demo/task.yaml`](../../../tasks/barplot_demo/task.yaml), [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml), [`tasks/boxplot_demo/task.yaml`](../../../tasks/boxplot_demo/task.yaml), [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/distance_matrix_demo/task.yaml`](../../../tasks/distance_matrix_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/ml_classification_route_demo/task.yaml`](../../../tasks/ml_classification_route_demo/task.yaml), [`tasks/ml_regression_route_demo/task.yaml`](../../../tasks/ml_regression_route_demo/task.yaml), [`tasks/permanova_demo/task.yaml`](../../../tasks/permanova_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml), [`tasks/reduce_pcoa_demo/task.yaml`](../../../tasks/reduce_pcoa_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/transpose_demo/task.yaml`](../../../tasks/transpose_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `order` | 维度顺序 | array |  |  |  | yes | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": {
      "param": "order",
      "default": []
    },
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "transpose"
}
```

## Processing rules (source docstring)

```text
Reorder the axes of a form.

Params:
    order  : list of dimension names, the desired new axis order
    output : context key for the result

--- module documentation ---

Transpose step: reorder the axes of a form.

Labels are unchanged: a label names a position along a named
dimension; only the axis order changes.
```

## Minimal YAML skeleton

```yaml
- name: transpose
  inputs: [<input1>]
  params:
    order: <array>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/transpose.md` and regenerate.
