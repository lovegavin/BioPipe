# power_t_test

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/power_t_test.py`](../../../src/task/step/steps/power_t_test.py)
- Tests: [`tests/test_extension70.py`](../../../tests/test_extension70.py), [`tests/test_r_oracles61.py`](../../../tests/test_r_oracles61.py)
- Demo tasks: none found
- Inputs arity: `0`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `test` | Test | string; enum=['two-sample', 'paired', 'one-sample'] | two-sample |  |  |  | basic |
| `effect_size` | Effect Size | number |  |  |  | yes | basic |
| `alpha` | 显著性水平 | number | 0.05 |  |  |  | advanced |
| `nobs1` | Nobs1 | integer |  | 2 |  | yes | basic |
| `nobs2` | Nobs2 | integer |  | 2 |  |  | basic |
| `ratio` | Ratio | number | 1.0 |  |  |  | basic |
| `alternative` | Alternative | string; enum=['two-sided', 'greater', 'less'] | two-sided |  |  |  | basic |
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
Compute achieved power for a t test from effect size and sample size.

--- module documentation ---

Achieved power for one- and two-sample t tests.
```

## Minimal YAML skeleton

```yaml
- name: power_t_test
  inputs: []
  params:
    test: <string; enum=['two-sample', 'paired', 'one-sample']>
    effect_size: <number>
    alpha: <number>
    nobs1: <integer>
    nobs2: <integer>
    ratio: <number>
    alternative: <string; enum=['two-sided', 'greater', 'less']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/power_t_test.md` and regenerate.
