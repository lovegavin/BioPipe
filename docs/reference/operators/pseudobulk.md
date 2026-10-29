# pseudobulk

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/pseudobulk.py`](../../../src/task/step/steps/pseudobulk.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `cell_dim` | Cell Dim | string | cell |  |  |  | basic |
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `method` | 方法 | string; enum=['sum', 'mean'] | sum |  |  |  | basic |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "cell_dim",
        "default": "cell"
      },
      {
        "param": "gene_dim",
        "default": "gene"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2
  },
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "cell_dim",
        "default": "cell"
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_any": [
      {
        "param": "group_label",
        "default": null
      }
    ]
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
    "info_open": false,
    "axis_info_open": false,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    }
  }
}
```

## Processing rules (source docstring)

```text
Aggregate single cells into sample/group-level pseudobulk profiles.

This is the standard pseudobulk operation: cells are grouped by a
metadata column, then summed or averaged per gene. It is deliberately
separate from differential expression; downstream tests decide whether
the pseudobulk matrix is used with limma/DESeq2 or descriptive plots.

Shared genes are kept in the input order; cells absent from metadata
are rejected rather than silently dropped.
```

## Minimal YAML skeleton

```yaml
- name: pseudobulk
  inputs: [<input1>, <input2>]
  params:
    cell_dim: <string>
    gene_dim: <string>
    group_label: <string>
    method: <string; enum=['sum', 'mean']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/pseudobulk.md` and regenerate.
