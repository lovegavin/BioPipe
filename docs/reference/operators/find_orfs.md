# find_orfs

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/find_orfs.py`](../../../src/task/step/steps/find_orfs.py)
- Tests: [`tasks/find_orfs_demo/test_find_orfs.py`](../../../tasks/find_orfs_demo/test_find_orfs.py), [`tasks/sequence_features_route_demo/test_sequence_route.py`](../../../tasks/sequence_features_route_demo/test_sequence_route.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py), [`tasks/verify_sequence_features.py`](../../../tasks/verify_sequence_features.py)
- Demo tasks: [`tasks/find_orfs_demo/task.yaml`](../../../tasks/find_orfs_demo/task.yaml), [`tasks/sequence_features_route_demo/task.yaml`](../../../tasks/sequence_features_route_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sequence_dim` | 序列维度 | string | sequence |  |  |  | basic |
| `position_dim` | 位置维度 | string | position |  |  |  | basic |
| `min_aa` | 最短氨基酸 | integer | 1 | 1 |  |  | basic |
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
Locate complete ATG..stop ORFs on both strands.

--- module documentation ---

Find complete ORFs (ATG..stop) in any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}.

Output:
    data   2D float32, shape (n_orfs, 6)
    dims   [orf, statistic]
    statistic = [strand, frame, start, end, length_nt, length_aa]
    info["sequence"] is axis-parallel to "orf", naming each ORF's
        source sequence label.

Both strands are scanned. Forward strand uses strand=+1; the reverse
complement uses strand=-1. For each chain, frames 0,1,2 start the
codon grid at that offset. From every ATG, the first in-frame stop
(TAA/TAG/TGA) closes an ORF. start and end are 0-based positions on
the chain that strand refers to; end is the last base of the stop
codon, so length_nt == end - start + 1 and length_aa == length_nt/3 - 1.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    min_aa       : minimum amino-acid count (default 1)
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: find_orfs
  inputs: [<input1>]
  params:
    sequence_dim: <string>
    position_dim: <string>
    min_aa: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/find_orfs.md` and regenerate.
