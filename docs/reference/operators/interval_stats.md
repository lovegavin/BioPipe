# interval_stats

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/interval_stats.py`](../../../src/task/step/steps/interval_stats.py)
- Tests: [`tasks/interval_route_demo/test_interval_route.py`](../../../tasks/interval_route_demo/test_interval_route.py), [`tasks/interval_stats_demo/test_interval_stats.py`](../../../tasks/interval_stats_demo/test_interval_stats.py), [`tasks/verify_interval_analysis.py`](../../../tasks/verify_interval_analysis.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/interval_analysis_demo/task.yaml`](../../../tasks/interval_analysis_demo/task.yaml), [`tasks/interval_route_demo/task.yaml`](../../../tasks/interval_route_demo/task.yaml), [`tasks/interval_stats_demo/task.yaml`](../../../tasks/interval_stats_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `region_dim` | 区间维度 | string | region |  |  |  | basic |
| `field_dim` | 字段维度 | string | field |  |  |  | advanced |
| `chrom_field` | 染色体列 | string | chrom |  |  |  | basic |
| `start_field` | 起始列 | string | chromStart |  |  |  | basic |
| `end_field` | 结束列 | string | chromEnd |  |  |  | basic |
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
      },
      "encoders": {
        "type": "object",
        "optional": true
      }
    },
    "dims": [
      {
        "param": "region_dim",
        "default": "region"
      },
      {
        "param": "field_dim",
        "default": "field"
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
Per-chromosome interval count and length statistics.

--- module documentation ---

Per-chromosome interval statistics for any BED-like Form.

Input: Form from BedReader (or any form with chrom/start/end columns).

Output:
    data   2D float32, shape (n_chroms, 7)
    dims   [chrom, statistic]
    statistic = [n_intervals, total_bp, mean_length, median_length,
                 min_length, max_length, span_bp]
    total_bp  = sum of (end - start) over all intervals
    span_bp   = max(end) - min(start) on this chrom
    median_length uses the middle value for odd counts, and the
    arithmetic mean of the two central values for even counts.

Params:
    region_dim  : record axis name (default "region")
    field_dim   : field axis name (default "field")
    chrom_field : chrom column label (default "chrom")
    start_field : start column label (default "chromStart")
    end_field   : end column label   (default "chromEnd")
    output      : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: interval_stats
  inputs: [<input1>]
  params:
    region_dim: <string>
    field_dim: <string>
    chrom_field: <string>
    start_field: <string>
    end_field: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/interval_stats.md` and regenerate.
