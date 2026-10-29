# doublet_detect

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/doublet_detect.py`](../../../src/task/step/steps/doublet_detect.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `cell_dim` | Cell Dim | string | cell |  |  |  | basic |
| `gene_dim` | Gene Dim | string | gene |  |  |  | basic |
| `expected_doublet_rate` | Expected Doublet Rate | number | 0.06 | 0 | 1 |  | basic |
| `random_state` | 随机种子 | integer | 0 |  |  |  | advanced |
| `threshold` | 阈值 | number | 0.25 | 0 | 1 |  | basic |
| `n_prin_comps` | N Prin Comps | integer | 20 | 2 |  |  | basic |
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
Per-cell doublet scores using Scanpy's Scrublet implementation.

Scrublet is the classic simulation-based doublet detector. The operator
wraps it directly, so the score and predicted-doublet threshold follow
the upstream implementation rather than a reimplementation.

Output is [cell, statistic] with columns doublet_score,
predicted_doublet and n_genes.
```

## Minimal YAML skeleton

```yaml
- name: doublet_detect
  inputs: [<input1>]
  params:
    cell_dim: <string>
    gene_dim: <string>
    expected_doublet_rate: <number>
    random_state: <integer>
    threshold: <number>
    n_prin_comps: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/doublet_detect.md` and regenerate.
