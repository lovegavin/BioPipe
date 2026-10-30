# egger_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/egger_test.py`](../../../src/task/step/steps/egger_test.py)
- Tests: [`tests/test_extension13.py`](../../../tests/test_extension13.py), [`tests/test_r_oracles5.py`](../../../tests/test_r_oracles5.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `study_dim` | Study Dim | string | study |  |  |  | basic |
| `statistic_dim` | Statistic Dim | string | statistic |  |  |  | basic |
| `effect_label` | Effect Label | string | effect |  |  |  | basic |
| `se_label` | Se Label | string | se |  |  |  | basic |
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
        "param": "study_dim",
        "default": "study"
      },
      {
        "param": "statistic_dim",
        "default": "statistic"
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
Egger's regression test for small-study effects in a meta-analysis.
```

## Minimal YAML skeleton

```yaml
- name: egger_test
  inputs: [<input1>]
  params:
    study_dim: <string>
    statistic_dim: <string>
    effect_label: <string>
    se_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/egger_test.md` and regenerate.
