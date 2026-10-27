# scatter

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-plots`
- Source: [`src/task/step/steps/scatter.py`](../../../src/task/step/steps/scatter.py)
- Tests: none found
- Demo tasks: [`tasks/annotation_qc_demo/task.yaml`](../../../tasks/annotation_qc_demo/task.yaml), [`tasks/bgen_qc_demo/task.yaml`](../../../tasks/bgen_qc_demo/task.yaml), [`tasks/gff_feature_stats_demo/task.yaml`](../../../tasks/gff_feature_stats_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/sequence_profiling_demo/task.yaml`](../../../tasks/sequence_profiling_demo/task.yaml), [`tasks/sequence_stats_demo/task.yaml`](../../../tasks/sequence_stats_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml)
- Inputs arity: `1`; output parameter: `None`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `alpha` | Opacity | number | 0.7 | 0 | 1 |  | advanced |
| `color_label` | Color field | string |  |  |  |  | basic |
| `dim` | 坐标维度 | string | feature |  |  |  | basic |
| `filename` | 文件名 | string |  |  |  | yes | basic |
| `point_size` | Point size | number | 8 | 0 |  |  | advanced |
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
      },
      {
        "dim": {
          "param": "dim",
          "default": "feature"
        },
        "values": {
          "param": "color_label",
          "default": null
        },
        "optional": true
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
Draw a scatter plot.

Params:
    dim         : attribute dimension (default "feature")
    x_label     : column label for the x axis
    y_label     : column label for the y axis
    color_label : optional column label for grouping
    filename    : output file name (e.g. "pca.png")
    title       : optional plot title
    xlabel      : optional x-axis label (default: x_label)
    ylabel      : optional y-axis label (default: y_label)
    point_size  : marker size (default 8)
    alpha       : marker transparency (default 0.7)

--- module documentation ---

Scatter plot operator.

Input is a single 2D form. One dimension of the form holds the
attributes (columns); the other dimension holds the observations
(points).

The operator reads two labeled columns as x and y, optionally a third
as a color group, and writes a scatter plot to ``output/figures/``.
```

## Minimal YAML skeleton

```yaml
- name: scatter
  inputs: [<input1>]
  params:
    alpha: <number>
    color_label: <string>
    dim: <string>
    filename: <string>
    point_size: <number>
    title: <string>
    x_label: <string>
    xlabel: <string>
    y_label: <string>
    ylabel: <string>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/scatter.md` and regenerate.
