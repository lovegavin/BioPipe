# gc_skew_profile

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/gc_skew_profile.py`](../../../src/task/step/steps/gc_skew_profile.py)
- Tests: [`tasks/gc_skew_demo/test_gc_skew_profile.py`](../../../tasks/gc_skew_demo/test_gc_skew_profile.py), [`tasks/verify_operators.py`](../../../tasks/verify_operators.py)
- Demo tasks: [`tasks/gc_skew_demo/task.yaml`](../../../tasks/gc_skew_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sequence_dim` | 序列维度 | string | sequence |  |  |  | basic |
| `position_dim` | 位置维度 | string | position |  |  |  | basic |
| `window_size` | 窗口大小 | integer | 10000 | 1 |  |  | basic |
| `step_size` | 步长 | integer / null | None | 1 |  |  | basic |
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
GC / AT composition and cumulative GC skew over sliding windows.

--- module documentation ---

Sliding-window GC and AT composition with cumulative GC skew.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna", "rna"}. The alphabet_map identifies
which numeric code stands for each of A, C, G, T; U is treated as T.

The input must contain exactly one sequence on the sequence axis.
Use select on the sequence axis first if the source has several.

For every window of window_size positions (default 10000), starting
at multiples of step_size (default = window_size):

    gc        (G + C) / valid
    at        (A + T) / valid
    gc_skew   (G - C) / (G + C)         NaN when G + C is zero
    cumulative_skew
              running (sum of G - C) / (running sum of G + C)
              accumulated across every window emitted so far, NaN
              when the running (G + C) is zero.
    cumulative_gc
              running sum of (G - C) across emitted windows.

valid counts A, C, G, T; N and other codes are excluded. NaN padding
at the end of the sequence is excluded as well. The last window may
be shorter than window_size when the sequence length is not a
multiple of step_size.

Output:
    data   2D float32, shape (n_windows, 7)
    dims   [window, statistic]
    statistic = (start, end, gc, at, gc_skew, cumulative_skew, cumulative_gc)
    start / end are 0-based half-open positions on the sequence.
    info["window_size"], info["step_size"], info["sequence_length"],
    info["representation"] = "gc_skew_profile".

Params:
    sequence_dim : sequence axis (default "sequence")
    position_dim : position axis (default "position")
    window_size  : window length in bases (default 10000)
    step_size    : step between window starts (default window_size)
    output       : context key (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: gc_skew_profile
  inputs: [<input1>]
  params:
    sequence_dim: <string>
    position_dim: <string>
    window_size: <integer>
    step_size: <integer / null>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/gc_skew_profile.md` and regenerate.
