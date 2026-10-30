# mantel

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/mantel.py`](../../../src/task/step/steps/mantel.py)
- Tests: [`tests/test_extension8.py`](../../../tests/test_extension8.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `n_perm` | N Perm | integer | 999 | 9 | 99999 |  | basic |
| `random_state` | 随机种子 | integer | 0 |  |  |  | advanced |
| `alternative` | Alternative | string; enum=['greater', 'less', 'two-sided'] | greater |  |  |  | basic |
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
  },
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
Mantel test between two square distance matrices.
```

## Minimal YAML skeleton

```yaml
- name: mantel
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    n_perm: <integer>
    random_state: <integer>
    alternative: <string; enum=['greater', 'less', 'two-sided']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/mantel.md` and regenerate.
