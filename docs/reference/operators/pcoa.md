# pcoa

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/pcoa.py`](../../../src/task/step/steps/pcoa.py)
- Tests: [`tests/test_extension75.py`](../../../tests/test_extension75.py), [`tests/test_r_oracles65.py`](../../../tests/test_r_oracles65.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `sample_b_dim` | Sample B Dim | string | sample_b |  |  |  | basic |
| `n_components` | 主成分数 | integer | 2 | 1 |  |  | basic |
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
        "param": "sample_dim",
        "default": "sample"
      },
      {
        "param": "sample_b_dim",
        "default": "sample_b"
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
Principal coordinates from a symmetric distance matrix.

--- module documentation ---

Classical principal coordinates analysis (PCoA).
```

## Minimal YAML skeleton

```yaml
- name: pcoa
  inputs: [<input1>]
  params:
    sample_dim: <string>
    sample_b_dim: <string>
    n_components: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/pcoa.md` and regenerate.
