# interval_overlap

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/interval_overlap.py`](../../../src/task/step/steps/interval_overlap.py)
- Tests: [`tasks/interval_overlap_demo/test_interval_overlap.py`](../../../tasks/interval_overlap_demo/test_interval_overlap.py), [`tasks/interval_route_demo/test_interval_route.py`](../../../tasks/interval_route_demo/test_interval_route.py), [`tasks/verify_interval_analysis.py`](../../../tasks/verify_interval_analysis.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/interval_analysis_demo/task.yaml`](../../../tasks/interval_analysis_demo/task.yaml), [`tasks/interval_overlap_demo/task.yaml`](../../../tasks/interval_overlap_demo/task.yaml), [`tasks/interval_route_demo/task.yaml`](../../../tasks/interval_route_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `a_region_dim` | A：区间维度 | string | region |  |  |  | basic |
| `a_field_dim` | A：字段维度 | string | field |  |  |  | basic |
| `a_chrom_field` | A：染色体列 | string | chrom |  |  |  | basic |
| `a_start_field` | A：起始列 | string | chromStart |  |  |  | basic |
| `a_end_field` | A：结束列 | string | chromEnd |  |  |  | basic |
| `b_region_dim` | B：区间维度 | string | region |  |  |  | basic |
| `b_field_dim` | B：字段维度 | string | field |  |  |  | basic |
| `b_chrom_field` | B：染色体列 | string | chrom |  |  |  | basic |
| `b_start_field` | B：起始列 | string | chromStart |  |  |  | basic |
| `b_end_field` | B：结束列 | string | chromEnd |  |  |  | basic |
| `min_overlap` | 最小重叠 | integer | 1 | 1 |  |  | basic |
| `max_output` | 最大输出数 | integer | 1000000 | 1 |  |  | basic |
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
        "param": "a_region_dim",
        "default": "region"
      },
      {
        "param": "a_field_dim",
        "default": "field"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  },
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
        "param": "b_region_dim",
        "default": "region"
      },
      {
        "param": "b_field_dim",
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
Pairwise overlap of intervals between two BED forms.

--- module documentation ---

Pairwise interval overlap between two BED forms (bedtools intersect style).

Inputs: two Forms from BedReader (or any form with chrom/start/end
columns). Each record is a half-open interval [start, end) on a chrom.

Output: every (A, B) pair whose intervals overlap by at least
``min_overlap`` bases.
    data   2D float32, shape (n_pairs, 7)
    dims   [pair, statistic]
    statistic = [overlap_start, overlap_end, overlap_length,
                 a_length, b_length,
                 overlap_fraction_a, overlap_fraction_b]
    info["chrom"]  axis-parallel, chromosome of each pair
    info["a_id"]   axis-parallel, index of the A interval
    info["b_id"]   axis-parallel, index of the B interval

Both inputs are grouped by chromosome and scanned with a sweep-line:
each A-start is matched against every currently open B interval, and
vice versa. Each pair is recorded exactly once.

Params:
    a_region_dim  : A record axis (default "region")
    a_field_dim   : A field axis (default "field")
    a_chrom_field : A chrom column (default "chrom")
    a_start_field : A start column (default "chromStart")
    a_end_field   : A end column (default "chromEnd")
    b_region_dim  : B record axis (default "region")
    b_field_dim   : B field axis (default "field")
    b_chrom_field : B chrom column (default "chrom")
    b_start_field : B start column (default "chromStart")
    b_end_field   : B end column (default "chromEnd")
    min_overlap   : minimum overlap in bp (default 1)
    max_output    : abort with an error above this many pairs (default 1000000)
    output        : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: interval_overlap
  inputs: [<input1>, <input2>]
  params:
    a_region_dim: <string>
    a_field_dim: <string>
    a_chrom_field: <string>
    a_start_field: <string>
    a_end_field: <string>
    b_region_dim: <string>
    b_field_dim: <string>
    b_chrom_field: <string>
    b_start_field: <string>
    b_end_field: <string>
    min_overlap: <integer>
    max_output: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/interval_overlap.md` and regenerate.
