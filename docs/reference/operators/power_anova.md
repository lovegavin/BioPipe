# power_anova

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/power_anova.py`](../../../src/task/step/steps/power_anova.py)
- Tests: [`tests/test_extension70.py`](../../../tests/test_extension70.py), [`tests/test_r_oracles61.py`](../../../tests/test_r_oracles61.py)
- Demo tasks: none found
- Inputs arity: `0`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `effect_size` | Effect Size | number |  |  |  | yes | basic |
| `n_per_group` | N Per Group | integer |  | 2 |  | yes | basic |
| `k_groups` | K Groups | integer |  | 2 |  | yes | basic |
| `alpha` | 显著性水平 | number | 0.05 |  |  |  | advanced |
| `output` | 输出名称 | string |  |  |  |  | basic |

## Input contract

```json
[]
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
Compute achieved power for a balanced one-way ANOVA.

--- module documentation ---

Achieved power for a balanced one-way ANOVA.
```

## Minimal YAML skeleton

```yaml
- name: power_anova
  inputs: []
  params:
    effect_size: <number>
    n_per_group: <integer>
    k_groups: <integer>
    alpha: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/power_anova.md` and regenerate.
