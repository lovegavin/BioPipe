# prs

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/prs.py`](../../../src/task/step/steps/prs.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `variant_dim` | Variant Dim | string | variant |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `stat_dim` | 统计维度 | string | statistic |  |  |  | advanced |
| `weight_label` | Weight Label | string | beta |  |  | yes | basic |
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
        "param": "sample_dim",
        "default": "sample"
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
        "param": "variant_dim",
        "default": "variant"
      },
      {
        "param": "stat_dim",
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
Polygenic risk score from aligned genotype dosages and variant weights.

Inputs
------
genotype : [variant, sample] allele dosage (0/1/2 or continuous dosage)
weights  : [variant, statistic] with a beta-weight column

The operator assumes the genotype dosage and weight are already aligned
to the same effect allele. It deliberately does not guess strand or
effect-allele orientation. Missing genotypes contribute zero and are
counted in the export; the score is therefore a complete-case dosage
sum over the variants present in both inputs.
```

## Minimal YAML skeleton

```yaml
- name: prs
  inputs: [<input1>, <input2>]
  params:
    variant_dim: <string>
    sample_dim: <string>
    stat_dim: <string>
    weight_label: <string>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/prs.md` and regenerate.
