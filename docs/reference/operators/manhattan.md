# manhattan

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/manhattan.py`](../../../src/task/step/steps/manhattan.py)
- Tests: none found
- Demo tasks: [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `alpha` | Opacity | number | 0.85 | 0 | 1 |  | advanced |
| `chrom_label` | 染色体字段 | string |  |  |  | yes | basic |
| `dim` | 变异维度 | string | feature |  |  |  | basic |
| `filename` | 文件名 | string |  |  |  | yes | basic |
| `p_dim` | 统计量维度 | string |  |  |  |  | basic |
| `p_label` | P 值标签 | string |  |  |  | yes | basic |
| `point_size` | Point size | number | 6 | 0 |  |  | advanced |
| `pos_label` | 位置字段 | string |  |  |  | yes | basic |
| `threshold` | Significance threshold | number |  |  |  |  | basic |
| `title` | Title | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": "feature"
      }
    ],
    "labels": [],
    "parallel": [
      {
        "dim": {
          "param": "dim",
          "default": "feature"
        },
        "fields": [
          {
            "param": "chrom_label",
            "default": null
          },
          {
            "param": "pos_label",
            "default": null
          }
        ],
        "allow_label": true
      },
      {
        "dim": {
          "param": "p_dim",
          "default": {
            "param": "dim",
            "default": "feature"
          }
        },
        "fields": [
          {
            "param": "p_label",
            "default": null
          }
        ],
        "allow_label": true
      }
    ],
    "ndim": 2
  }
]
```

## Output contract

```json
{
  "mode": "report"
}
```

## Processing rules (source docstring)

```text
Draw a Manhattan plot.

    Params:
        dim         : observation dim (one point per position)
        chrom_label : chromosome field on ``dim``
        pos_label   : position field on ``dim``
        p_label     : P-value field
        p_dim       : dim carrying ``p_label`` (default: ``dim``)
        filename    : output file name
        threshold   : optional P threshold for a horizontal line
        title       : optional plot title
        point_size  : marker size (default 6)
        alpha       : marker transparency (default 0.85)

--- module documentation ---

Manhattan plot operator.

Input is a single 2D form. The operator draws a genome-wide scatter
of -log10(P) against cumulative genomic position.

Field locations
---------------
Each field is looked up either as a data column on a named dimension
or as an axis-parallel info entry. ``chrom_label`` and ``pos_label``
are looked up on ``dim``; ``p_label`` is looked up on ``p_dim``
(default: ``dim``). This lets chromosome/position come from one
dimension and the P value from another.

Chromosome values are kept as they appear (typically strings such as
``"22"``). They are grouped, ordered and labelled verbatim; no
encoding is applied.
```

## Minimal YAML skeleton

```yaml
- name: manhattan
  inputs: [<input1>]
  params:
    alpha: <number>
    chrom_label: <string>
    dim: <string>
    filename: <string>
    p_dim: <string>
    p_label: <string>
    point_size: <number>
    pos_label: <string>
    threshold: <number>
    title: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/manhattan.md` and regenerate.
