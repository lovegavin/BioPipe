# interval_merge

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/interval_merge.py`](../../../src/task/step/steps/interval_merge.py)
- Tests: [`tasks/interval_merge_demo/test_interval_merge.py`](../../../tasks/interval_merge_demo/test_interval_merge.py), [`tasks/interval_route_demo/test_interval_route.py`](../../../tasks/interval_route_demo/test_interval_route.py), [`tasks/verify_interval_analysis.py`](../../../tasks/verify_interval_analysis.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py), [`tests/test_reader_precision.py`](../../../tests/test_reader_precision.py)
- Demo tasks: [`tasks/interval_analysis_demo/task.yaml`](../../../tasks/interval_analysis_demo/task.yaml), [`tasks/interval_merge_demo/task.yaml`](../../../tasks/interval_merge_demo/task.yaml), [`tasks/interval_route_demo/task.yaml`](../../../tasks/interval_route_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `region_dim` | 区间维度 | string | region |  |  |  | basic |
| `field_dim` | 字段维度 | string | field |  |  |  | advanced |
| `chrom_field` | 染色体列 | string | chrom |  |  |  | basic |
| `start_field` | 起始列 | string | chromStart |  |  |  | basic |
| `end_field` | 结束列 | string | chromEnd |  |  |  | basic |
| `min_overlap` | 最小重叠 | integer | 0 | 0 |  |  | basic |
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
Merge overlapping BED intervals per chromosome.

--- module documentation ---

Merge overlapping BED intervals per chromosome (bedtools merge style).

Input: Form from BedReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [region, field]
    labels field = BED column names (chrom, chromStart, chromEnd, ...)
    info   missing_code=NaN, encoders={field: {label: encoder}}

Only chrom, chromStart and chromEnd are read. Records are grouped
by chromosome, sorted by start, and consecutive intervals are merged
when the gap between them is at most ``min_overlap`` bases:

    gap = next.start - current.end
    merge when gap <= min_overlap

With min_overlap=0, overlapping and book-ended intervals (gap == 0)
are merged. Negative gaps (real overlap) are always merged.

Output:
    data   2D float32, shape (n_merged, 4)
    dims   [merged_region, statistic]
    statistic = [start, end, length, n_intervals]
    length = end - start (0-based half-open)
    info["chrom"]  axis-parallel, chromosome of each merged region

Params:
    region_dim  : name of the record axis (default "region")
    field_dim   : name of the field axis (default "field")
    chrom_field : name of the chrom column (default "chrom")
    start_field : name of the start column (default "chromStart")
    end_field   : name of the end column   (default "chromEnd")
    min_overlap : merge intervals whose gap is <= this value (default 0)
    output      : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: interval_merge
  inputs: [<input1>]
  params:
    region_dim: <string>
    field_dim: <string>
    chrom_field: <string>
    start_field: <string>
    end_field: <string>
    min_overlap: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/interval_merge.md` and regenerate.
