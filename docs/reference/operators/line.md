# line

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/line.py`](../../../src/task/step/steps/line.py)
- Tests: none found
- Demo tasks: [`tasks/gc_skew_demo/task.yaml`](../../../tasks/gc_skew_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 维度 | string | feature |  |  |  | basic |
| `filename` | 文件名 | string |  |  |  | yes | basic |
| `sort` | Sort by X | boolean | True |  |  |  | basic |
| `title` | Title | string |  |  |  |  | basic |
| `x_label` | 横坐标标签 | string |  |  |  | yes | basic |
| `xlabel` | X axis label | string |  |  |  |  | basic |
| `y_label` | 纵坐标标签 | string |  |  |  | yes | basic |
| `ylabel` | Y axis label | string |  |  |  |  | basic |

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
    "labels": [
      {
        "dim": {
          "param": "dim",
          "default": "feature"
        },
        "values": [
          {
            "param": "x_label",
            "default": null
          },
          {
            "param": "y_label",
            "default": null
          }
        ]
      }
    ],
    "parallel": [],
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
Draw a line plot.

Params:
    dim      : attribute dimension (default "feature")
    x_label  : column label for the x axis
    y_label  : column label for the y axis
    filename : output file name
    title    : optional plot title
    xlabel   : optional x-axis label (default: x_label)
    ylabel   : optional y-axis label (default: y_label)
    sort     : sort points by x before drawing (default True)

--- module documentation ---

Line plot operator.

Input is a single 2D form. One dimension holds the attributes
(columns); the other holds the observations. The operator reads two
labeled columns as x and y, sorts by x, and draws a line.
```

## Minimal YAML skeleton

```yaml
- name: line
  inputs: [<input1>]
  params:
    dim: <string>
    filename: <string>
    sort: <boolean>
    title: <string>
    x_label: <string>
    xlabel: <string>
    y_label: <string>
    ylabel: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/line.md` and regenerate.
