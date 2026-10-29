# nmf

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/nmf.py`](../../../src/task/step/steps/nmf.py)
- Tests: [`tests/test_extension3.py`](../../../tests/test_extension3.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `n_components` | 主成分数 | integer | 5 | 1 |  |  | basic |
| `init` | Init | string; enum=['nndsvda', 'nndsvd', 'random'] | nndsvda |  |  |  | basic |
| `max_iter` | Max Iter | integer | 500 | 10 |  |  | basic |
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
        "param": "sample_dim",
        "default": "sample"
      },
      {
        "param": "feature_dim",
        "default": "feature"
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
Non-negative matrix factorisation of a sample x feature matrix.
```

## Minimal YAML skeleton

```yaml
- name: nmf
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    n_components: <integer>
    init: <string; enum=['nndsvda', 'nndsvd', 'random']>
    max_iter: <integer>
    random_state: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/nmf.md` and regenerate.
