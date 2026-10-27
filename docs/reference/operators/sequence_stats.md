# sequence_stats

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/sequence_stats.py`](../../../src/task/step/steps/sequence_stats.py)
- Tests: [`tasks/sequence_features_route_demo/test_sequence_route.py`](../../../tasks/sequence_features_route_demo/test_sequence_route.py), [`tasks/sequence_stats_demo/test_sequence_stats.py`](../../../tasks/sequence_stats_demo/test_sequence_stats.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py), [`tasks/verify_sequence_features.py`](../../../tasks/verify_sequence_features.py)
- Demo tasks: [`tasks/sequence_features_route_demo/task.yaml`](../../../tasks/sequence_features_route_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml), [`tasks/sequence_stats_demo/task.yaml`](../../../tasks/sequence_stats_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sequence_dim` | 序列维度 | string | sequence |  |  |  | basic |
| `position_dim` | 位置维度 | string | position |  |  |  | basic |
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
Per-sequence length, GC and N content for any sequence-codes Form.

--- module documentation ---

Per-sequence summary statistics for sequence-codes forms.

Input: any Form declaring info["representation"] == "sequence_codes".
The character-to-code mapping is read from info["alphabet_map"], so
the operator works with any reader that declares the same convention
(FASTA today; FASTQ, 2bit, GenBank, ... later).

Output: [sequence, statistic] float32 with
    length       number of non-padding positions
    gc           (C + G) / length
    n_ratio      N / length
    valid_ratio  length / max_position

Only DNA/RNA alphabets (info["alphabet"] in {"dna","rna"}) are accepted;
GC content is undefined for protein.

Params:
    sequence_dim : name of the sequence axis (default "sequence")
    position_dim : name of the position axis (default "position")
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: sequence_stats
  inputs: [<input1>]
  params:
    sequence_dim: <string>
    position_dim: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/sequence_stats.md` and regenerate.
