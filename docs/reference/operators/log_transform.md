# log_transform

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/log_transform.py`](../../../src/task/step/steps/log_transform.py)
- Tests: [`tasks/ml_classification_route_demo/test_ml_classification.py`](../../../tasks/ml_classification_route_demo/test_ml_classification.py), [`tasks/ml_regression_route_demo/test_ml_regression.py`](../../../tasks/ml_regression_route_demo/test_ml_regression.py), [`tasks/multi_omics_route_demo/test_multi_omics_route.py`](../../../tasks/multi_omics_route_demo/test_multi_omics_route.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_ml_classification.py`](../../../tasks/verify_ml_classification.py), [`tasks/verify_ml_regression.py`](../../../tasks/verify_ml_regression.py), [`tasks/verify_multi_omics.py`](../../../tasks/verify_multi_omics.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/boxplot_demo/task.yaml`](../../../tasks/boxplot_demo/task.yaml), [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/correlation_demo/task.yaml`](../../../tasks/correlation_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/heatmap_demo/task.yaml`](../../../tasks/heatmap_demo/task.yaml), [`tasks/log_transform_demo/task.yaml`](../../../tasks/log_transform_demo/task.yaml), [`tasks/ml_classification_route_demo/task.yaml`](../../../tasks/ml_classification_route_demo/task.yaml), [`tasks/ml_regression_route_demo/task.yaml`](../../../tasks/ml_regression_route_demo/task.yaml), [`tasks/multi_omics_route_demo/task.yaml`](../../../tasks/multi_omics_route_demo/task.yaml), [`tasks/rank_axis_demo/task.yaml`](../../../tasks/rank_axis_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scale_features_demo/task.yaml`](../../../tasks/scale_features_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `base` | 底数 | any; enum=[2, 10, 'e'] | 2 |  |  |  | basic |
| `pseudocount` | 伪计数 | number | 1 | 0 |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [],
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "transform",
  "representation": "log_transform"
}
```

## Processing rules (source docstring)

```text
Apply log_base(x + pseudocount) elementwise.

--- module documentation ---

Log-transform a Form.

Applies log_base(x + pseudocount) elementwise. Standard third step
after normalization, for any count-based matrix (RNA-seq,
single-cell, metagenomics, proteomics).

Missing values are preserved: any cell that is missing on input
stays missing on output. ``dims``, ``labels``, ``info`` and
``axis_info`` are passed through unchanged.

Params:
    base        : log base, either 2, 10, "e" (default 2)
    pseudocount : value added before the log (default 1)
    output      : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: log_transform
  inputs: [<input1>]
  params:
    base: <any; enum=[2, 10, 'e']>
    pseudocount: <number>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/log_transform.md` and regenerate.
