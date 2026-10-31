# hardy_weinberg

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/hardy_weinberg.py`](../../../src/task/step/steps/hardy_weinberg.py)
- Tests: [`tests/test_extension77.py`](../../../tests/test_extension77.py), [`tests/test_r_oracles67.py`](../../../tests/test_r_oracles67.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `variant_dim` | Variant Dim | string | variant |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `aa_label` | Aa Label | string | AA |  |  |  | basic |
| `ab_label` | Ab Label | string | AB |  |  |  | basic |
| `bb_label` | Bb Label | string | BB |  |  |  | basic |
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
        "param": "variant_dim",
        "default": "variant"
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
Exact and descriptive Hardy-Weinberg statistics for biallelic variants.

--- module documentation ---

Exact Hardy-Weinberg equilibrium test for biallelic genotypes.
```

## Minimal YAML skeleton

```yaml
- name: hardy_weinberg
  inputs: [<input1>]
  params:
    variant_dim: <string>
    feature_dim: <string>
    aa_label: <string>
    ab_label: <string>
    bb_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/hardy_weinberg.md` and regenerate.
