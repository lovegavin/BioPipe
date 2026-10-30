# cell_cycle_score

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cell_cycle_score.py`](../../../src/task/step/steps/cell_cycle_score.py)
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `cell_dim` | Cell Dim | string | cell |  |  |  | basic |
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `gene_set_dim` | Gene Set Dim | string | gene_set |  |  |  | basic |
| `ctrl_size` | Ctrl Size | integer | 50 | 1 |  |  | basic |
| `n_bins` | N Bins | integer | 25 | 1 |  |  | basic |
| `random_state` | 随机种子 | integer | 0 |  |  |  | advanced |
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
        "param": "gene_dim",
        "default": "gene"
      },
      {
        "param": "gene_set_dim",
        "default": "gene_set"
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
    "axis_info_open": false
  }
}
```

## Processing rules (source docstring)

```text
Cell-cycle S/G2M scores and phase assignment (Scanpy score_genes).
```

## Minimal YAML skeleton

```yaml
- name: cell_cycle_score
  inputs: [<input1>, <input2>]
  params:
    cell_dim: <string>
    gene_dim: <string>
    gene_set_dim: <string>
    ctrl_size: <integer>
    n_bins: <integer>
    random_state: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cell_cycle_score.md` and regenerate.
