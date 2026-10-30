# restriction_sites

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/restriction_sites.py`](../../../src/task/step/steps/restriction_sites.py)
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sequence_dim` | 序列维度 | string | sequence |  |  |  | basic |
| `position_dim` | 位置维度 | string | position |  |  |  | basic |
| `enzymes` | Enzymes | object | {'EcoRI': 'GAATTC', 'BamHI': 'GGATCC', 'HindIII': 'AAGCTT', 'NotI': 'GCGGCCGC', 'XhoI': 'CTCGAG', 'PstI': 'CTGCAG', 'SalI': 'GTCGAC', 'KpnI': 'GGTACC', 'SacI': 'GAGCTC', 'SmaI': 'CCCGGG', 'TaqI': 'TCGA', 'AluI': 'AGCT'} |  |  |  | basic |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {
      "representation": {
        "type": "string",
        "const": "sequence_codes"
      },
      "alphabet": {
        "type": "string",
        "enum": [
          "dna"
        ]
      },
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    },
    "dims": [
      {
        "param": "sequence_dim",
        "default": "sequence"
      },
      {
        "param": "position_dim",
        "default": "position"
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
Count restriction-enzyme recognition sites in DNA sequences.
```

## Minimal YAML skeleton

```yaml
- name: restriction_sites
  inputs: [<input1>]
  params:
    sequence_dim: <string>
    position_dim: <string>
    enzymes: <object>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/restriction_sites.md` and regenerate.
