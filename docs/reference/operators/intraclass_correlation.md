# intraclass_correlation

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/intraclass_correlation.py`](../../../src/task/step/steps/intraclass_correlation.py)
- Tests: [`tests/test_extension25.py`](../../../tests/test_extension25.py), [`tests/test_r_oracles17.py`](../../../tests/test_r_oracles17.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `raters` | Raters | array |  |  |  |  | basic |
| `model` | Model | string; enum=['oneway', 'twoway'] | twoway |  |  |  | basic |
| `type` | Type | string; enum=['consistency', 'agreement'] | agreement |  |  |  | basic |
| `unit` | Unit | string; enum=['single', 'average'] | single |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
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
Intraclass correlation coefficients, ported from R irr::icc.
```

## Minimal YAML skeleton

```yaml
- name: intraclass_correlation
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    raters: <array>
    model: <string; enum=['oneway', 'twoway']>
    type: <string; enum=['consistency', 'agreement']>
    unit: <string; enum=['single', 'average']>
    confidence: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/intraclass_correlation.md` and regenerate.
