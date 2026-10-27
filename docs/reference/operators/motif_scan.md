# motif_scan

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/motif_scan.py`](../../../src/task/step/steps/motif_scan.py)
- Tests: [`tasks/motif_scan_demo/test_motif_scan.py`](../../../tasks/motif_scan_demo/test_motif_scan.py), [`tasks/sequence_features_route_demo/test_sequence_route.py`](../../../tasks/sequence_features_route_demo/test_sequence_route.py), [`tasks/verify_sequence_features.py`](../../../tasks/verify_sequence_features.py)
- Demo tasks: [`tasks/motif_scan_demo/task.yaml`](../../../tasks/motif_scan_demo/task.yaml), [`tasks/sequence_features_route_demo/task.yaml`](../../../tasks/sequence_features_route_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sequence_dim` | 序列维度 | string | sequence |  |  |  | basic |
| `position_dim` | 位置维度 | string | position |  |  |  | basic |
| `motifs` | 模体列表 | object |  |  |  | yes | basic |
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
      "representation": {
        "type": "string",
        "const": "sequence_codes"
      },
      "alphabet_map": {
        "type": "object"
      },
      "unknown_code": {
        "type": "integer"
      },
      "alphabet": {
        "type": "string",
        "enum": [
          "dna",
          "rna"
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
    "info_open": true,
    "axis_info_open": true
  }
}
```

## Processing rules (source docstring)

```text
Count IUPAC motif occurrences per sequence.

--- module documentation ---

Scan IUPAC motifs across any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}.

Motifs come in as {"name": "IUPAC-pattern"} and are matched on the
forward strand. Each window of the same length is compared using the
IUPAC convention:

    A C G T U -> single base
    R = A|G    Y = C|T    S = G|C    W = A|T
    K = G|T    M = A|C    B = C|G|T  D = A|G|T
    H = A|C|T  V = A|C|G  N = any

Output:
    data   2D float32, shape (n_motifs, n_sequences)
    dims   [motif, sequence]
    labels motif = user-supplied names, in insertion order
           sequence = input sequence labels

Counts include overlapping occurrences. Windows crossing N, unknown
codes or the NaN padding are skipped.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    motifs       : {"name": "IUPAC-string"} mapping (required)
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: motif_scan
  inputs: [<input1>]
  params:
    sequence_dim: <string>
    position_dim: <string>
    motifs: <object>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/motif_scan.md` and regenerate.
