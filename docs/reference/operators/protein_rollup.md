# protein_rollup

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/protein_rollup.py`](../../../src/task/step/steps/protein_rollup.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `peptide_dim` | Peptide Dim | string | peptide |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `protein_dim` | Protein Dim | string | protein |  |  |  | basic |
| `method` | 方法 | string; enum=['sum', 'mean'] | sum |  |  |  | basic |
| `min_peptides` | Min Peptides | integer | 1 | 1 |  |  | basic |
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
        "param": "peptide_dim",
        "default": "peptide"
      },
      {
        "param": "sample_dim",
        "default": "sample"
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
        "param": "peptide_dim",
        "default": "peptide"
      },
      {
        "param": "protein_dim",
        "default": "protein"
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
Roll up peptide intensities to protein-level profiles.

Inputs
------
peptides : [peptide, sample] peptide intensity matrix
mapping  : [peptide, protein] binary peptide-to-protein membership

A peptide may map to more than one protein; its values contribute to
every mapped protein. The aggregation rule is explicit (sum/mean).
Peptides absent from the mapping are excluded and counted. This is the
standard rollup ambiguity, not a silent one-to-one assumption.
```

## Minimal YAML skeleton

```yaml
- name: protein_rollup
  inputs: [<input1>, <input2>]
  params:
    peptide_dim: <string>
    sample_dim: <string>
    protein_dim: <string>
    method: <string; enum=['sum', 'mean']>
    min_peptides: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/protein_rollup.md` and regenerate.
