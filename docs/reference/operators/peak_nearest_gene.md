# peak_nearest_gene

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/peak_nearest_gene.py`](../../../src/task/step/steps/peak_nearest_gene.py)
- Tests: [`tasks/peak_nearest_gene_demo/test_peak_nearest_gene.py`](../../../tasks/peak_nearest_gene_demo/test_peak_nearest_gene.py), [`tasks/peak_nearest_gene_demo/test_peak_nearest_gene_gtf.py`](../../../tasks/peak_nearest_gene_demo/test_peak_nearest_gene_gtf.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/peak_nearest_gene_demo/task.yaml`](../../../tasks/peak_nearest_gene_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `a_region_dim` | A：区间维度 | string | region |  |  |  | basic |
| `a_field_dim` | A：字段维度 | string | field |  |  |  | basic |
| `a_chrom_field` | A：染色体列 | string | chrom |  |  |  | basic |
| `a_start_field` | A：起始列 | string | chromStart |  |  |  | basic |
| `a_end_field` | A：结束列 | string | chromEnd |  |  |  | basic |
| `b_record_dim` | B：记录维度 | string | record |  |  |  | basic |
| `b_field_dim` | B：字段维度 | string | field |  |  |  | basic |
| `b_chrom_field` | B：染色体列 | string | auto |  |  |  | basic |
| `b_type_field` | B：类型列 | string | auto |  |  |  | basic |
| `b_attr_field` | B：属性列 | string | auto |  |  |  | basic |
| `b_start_field` | B：起始列 | string | start |  |  |  | basic |
| `b_end_field` | B：结束列 | string | end |  |  |  | basic |
| `b_strand_field` | B：链方向列 | string | strand |  |  |  | basic |
| `feature_type` | 特征类型 | string | gene |  |  |  | basic |
| `max_distance` | 最大距离 | integer / null | None | 0 |  |  | basic |
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
        "param": "b_record_dim",
        "default": "record"
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
Assign every BED interval to its nearest annotated gene.

--- module documentation ---

Associate every BED interval with its nearest annotated gene.

Inputs:
    A  BED     [region, field]  with chrom / chromStart / chromEnd
    B  GFF3/GTF [record, field]  with a seqid column (``seqid`` for
                GFF3, ``seqname`` for GTF), a feature-type column
                (``type`` or ``feature``), start / end / strand, and
                optionally an attributes column (``attributes`` or
                ``attribute``).

For every A interval, find the gene record on the same chromosome
whose span is closest. Overlapping intervals get distance 0.

Distance:
    overlap          -> 0
    A ends before B  -> B.start - A.end
    A starts after B -> A.start - B.end

Chromosome names are normalised before matching: ``chr`` is added
if missing, and the common mitochondrial aliases ``Mito``, ``MT``
and ``chrM`` are unified. A column may or may not be encoded: if the
reader encoded it, the encoder's inverse is used; otherwise the
numeric value is stringified without a trailing ``.0``.

Output:
    data   2D float32, shape (n_peaks, 5)
    dims   [peak, statistic]
    statistic = [distance, gene_start, gene_end, gene_length, strand]
    info["peak_id"]  axis-parallel, index of the A interval
    info["gene_id"]  axis-parallel, gene id from attributes or "g<i>"
    info["chrom"]    axis-parallel, normalised chromosome name

Params:
    a_region_dim   : A record axis  (default "region")
    a_field_dim    : A field axis   (default "field")
    a_chrom_field  : A chrom column (default "chrom")
    a_start_field  : A start column (default "chromStart")
    a_end_field    : A end column   (default "chromEnd")
    b_record_dim   : B record axis  (default "record")
    b_field_dim    : B field axis   (default "field")
    b_chrom_field  : B seqid column. Default "auto" resolves via the
                     role aliases ("seqid", "seqname").
    b_type_field   : B feature-type column. Default "auto" resolves
                     via ("type", "feature").
    b_attr_field   : B attributes column. Default "auto" resolves
                     via ("attributes", "attribute"), or None if
                     neither is present.
    b_start_field  : B start column (default "start")
    b_end_field    : B end column   (default "end")
    b_strand_field : B strand column (default "strand")
    feature_type   : only use B records whose type equals this
                     (default "gene"; set to "" to disable)
    max_distance   : report only peaks with distance <= this many bp
                     (default null = no limit)
    output         : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: peak_nearest_gene
  inputs: [<input1>, <input2>]
  params:
    a_region_dim: <string>
    a_field_dim: <string>
    a_chrom_field: <string>
    a_start_field: <string>
    a_end_field: <string>
    b_record_dim: <string>
    b_field_dim: <string>
    b_chrom_field: <string>
    b_type_field: <string>
    b_attr_field: <string>
    b_start_field: <string>
    b_end_field: <string>
    b_strand_field: <string>
    feature_type: <string>
    max_distance: <integer / null>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/peak_nearest_gene.md` and regenerate.
