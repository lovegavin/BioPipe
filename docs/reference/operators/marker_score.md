# marker_score

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/marker_score.py`](../../../src/task/step/steps/marker_score.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `cell_dim` | Cell Dim | string | cell |  |  |  | basic |
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `gene_set_dim` | Gene Set Dim | string | gene_set |  |  |  | basic |
| `min_genes` | Min Genes | integer | 1 | 1 |  |  | basic |
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
Abstract step.

Subclasses declare:

* ``name`` — matched against the manifest's ``name`` field.
* ``inputs_arity`` — number of input forms, or ``"*"`` for any.
* ``outputs`` — context keys the step registers on exit.

And implement ``run``. They may also implement ``export`` to
return a JSON-serializable dict of the step's full results.

--- module documentation ---

Per-cell signature scores using Scanpy's score_genes.

The input gene sets are a binary [gene, gene_set] matrix, normally
produced by GmtReader. For every set Scanpy's control-gene-corrected
score is computed; genes absent from the expression matrix are skipped
and reported. This is the standard scanpy/Seurat-style signature score,
not a proprietary marker ranking.
```

## Minimal YAML skeleton

```yaml
- name: marker_score
  inputs: [<input1>, <input2>]
  params:
    cell_dim: <string>
    gene_dim: <string>
    gene_set_dim: <string>
    min_genes: <integer>
    ctrl_size: <integer>
    n_bins: <integer>
    random_state: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/marker_score.md` and regenerate.
