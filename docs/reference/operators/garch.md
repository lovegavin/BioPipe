# garch

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/garch.py`](../../../src/task/step/steps/garch.py)
- Tests: [`tests/test_extension69.py`](../../../tests/test_extension69.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `value_label` | 数值字段 | string |  |  |  | yes | basic |
| `mean` | Mean | string; enum=['Constant', 'Zero'] | Constant |  |  |  | basic |
| `p` | P | integer | 1 | 1 | 3 |  | basic |
| `q` | Q | integer | 1 | 1 | 3 |  | basic |
| `dist` | Dist | string; enum=['normal', 't'] | normal |  |  |  | basic |
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
Fit a GARCH(p, q) model with a constant or zero mean.

--- module documentation ---

GARCH volatility model.
```

## Minimal YAML skeleton

```yaml
- name: garch
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    value_label: <string>
    mean: <string; enum=['Constant', 'Zero']>
    p: <integer>
    q: <integer>
    dist: <string; enum=['normal', 't']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/garch.md` and regenerate.
