# kmer_count

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/kmer_count.py`](../../../src/task/step/steps/kmer_count.py)
- Tests: [`tasks/kmer_count_demo/test_kmer_count.py`](../../../tasks/kmer_count_demo/test_kmer_count.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/kmer_count_demo/task.yaml`](../../../tasks/kmer_count_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sequence_dim` | 序列维度 | string | sequence |  |  |  | basic |
| `position_dim` | 位置维度 | string | position |  |  |  | basic |
| `k` | k-mer 长度 | integer | 3 | 1 | 6 |  | basic |
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
Count k-mers per sequence for any sequence-codes Form.

--- module documentation ---

k-mer counts per sequence for any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}. The character-to-code mapping
comes from info["alphabet_map"], so the operator works with any reader
declaring the same convention.

Output:
    data   2D float32, shape (n_kmers, n_sequences)
    dims   [kmer, sequence]
    labels kmer = every A/C/G/T word of length k, in lexicographic order
           sequence = the input's sequence labels

Only fully A/C/G/T windows are counted. Windows containing N or any
other code are skipped. Different sequence lengths are handled by the
input's NaN padding; windows that would extend past the last defined
position are skipped.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    k            : word length, 1..6 (default 3)
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: kmer_count
  inputs: [<input1>]
  params:
    sequence_dim: <string>
    position_dim: <string>
    k: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/kmer_count.md` and regenerate.
