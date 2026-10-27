# qc_metrics

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/qc_metrics.py`](../../../src/task/step/steps/qc_metrics.py)
- Tests: [`tasks/qc_metrics_demo/test_qc_metrics.py`](../../../tasks/qc_metrics_demo/test_qc_metrics.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tests/sop/test_core_operators_sop.py`](../../../tests/sop/test_core_operators_sop.py)
- Demo tasks: [`tasks/qc_metrics_demo/task.yaml`](../../../tasks/qc_metrics_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `metrics` | 指标 | array |  |  |  | yes | basic |
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
Per-sample summary metrics along a feature axis.

--- module documentation ---

Per-sample summary metrics along a feature axis.

Input: any 2D Form with axes [feature_dim, sample_dim].

For each declared metric, a summary is computed along the feature
axis, producing one value per sample. A metric may restrict itself
to features whose label starts with a given prefix, and may divide
its raw result by another metric declared in the same call.

Metrics
-------
op values and their meaning over the selected feature subset:
    sum      sum of non-missing values
    mean     arithmetic mean of non-missing values
    std      population standard deviation (ddof=0)
    var      population variance (ddof=0)
    min      minimum of non-missing values
    max      maximum of non-missing values
    count    number of non-missing values
    nonzero  number of non-missing and non-zero values

Missing cells are recognised from info["missing_code"]: when that
code is NaN, non-finite cells count as missing.

Output:
    data   2D float32, shape (n_samples, n_metrics)
    dims   [sample_dim, statistic]
    statistic labels are the metric names, in declaration order.

Params:
    feature_dim : feature axis (default "feature")
    sample_dim  : sample axis  (default "sample")
    metrics     : list of {"name", "op", "feature_pattern"?, "divide_by"?}
    output      : context key (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: qc_metrics
  inputs: [<input1>]
  params:
    feature_dim: <string>
    sample_dim: <string>
    metrics: <array>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/qc_metrics.md` and regenerate.
