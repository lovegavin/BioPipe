# gene_structure

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/gene_structure.py`](../../../src/task/step/steps/gene_structure.py)
- Tests: [`tasks/gene_structure_demo/test_gene_structure.py`](../../../tasks/gene_structure_demo/test_gene_structure.py), [`tasks/gtf_annotation_demo/test_gtf_annotation.py`](../../../tasks/gtf_annotation_demo/test_gtf_annotation.py), [`tasks/verify_gtf_annotation.py`](../../../tasks/verify_gtf_annotation.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/annotation_qc_demo/task.yaml`](../../../tasks/annotation_qc_demo/task.yaml), [`tasks/gene_structure_demo/task.yaml`](../../../tasks/gene_structure_demo/task.yaml), [`tasks/gtf_annotation_demo/task.yaml`](../../../tasks/gtf_annotation_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `record_dim` | 记录维度 | string | record |  |  |  | basic |
| `field_dim` | 字段维度 | string | field |  |  |  | advanced |
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
        "param": "record_dim",
        "default": "record"
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
Per-gene exon/intron/CDS summary for GFF3/GTF annotations.

--- module documentation ---

Per-gene structure summary for any GFF3 / GTF Form.

Input: Form from Gff3Reader or GtfReader.
    data   2D float32, shape (n_records, n_fields)
    dims   [record, field]
    labels field includes seqid / type / start / end / strand, plus
           optionally attributes (GFF3: 'attributes', GTF: 'attribute')
    info   missing_code=NaN, encoders={field: {column: encoder}}

Every record whose feature type is exactly "gene" becomes one output
row. Exon and CDS records are attributed to their parent gene using
the annotation's own parent chain:

  * GTF: each exon / CDS record carries ``gene_id "X"`` directly.
  * GFF3: each exon / CDS record carries ``Parent=transcript:Y``; the
    transcript record Y carries ``Parent=gene:X``.

Records whose parent chain resolves to a gene that is not in the
"gene" feature set (for example an exon of an ``ncRNA_gene``) are
skipped. When a record carries no attribute information at all
(minimal fixtures), the operator falls back to span containment: the
record is attributed to the first gene whose span on the same
sequence contains it. Span containment mis-attributes nested genes,
so it is used only when the parent chain is unavailable.

Output:
    data   2D float32, shape (n_genes, 5)
    dims   [gene, statistic]
    statistic = (n_exons, n_introns, gene_length, cds_total, strand)

Params:
    record_dim : record axis (default "record")
    field_dim  : field axis  (default "field")
    output     : context key (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: gene_structure
  inputs: [<input1>]
  params:
    record_dim: <string>
    field_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/gene_structure.md` and regenerate.
