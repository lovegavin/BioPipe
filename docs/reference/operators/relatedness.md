# relatedness

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/relatedness.py`](../../../src/task/step/steps/relatedness.py)
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `variant_dim` | Variant Dim | string | variant |  |  |  | basic |
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `min_maf` | Min Maf | number | 0.05 | 0 | 0.5 |  | basic |
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
Genomic relationship matrix from genotype dosages.
```

## Minimal YAML skeleton

```yaml
- name: relatedness
  inputs: [<input1>]
  params:
    variant_dim: <string>
    sample_dim: <string>
    min_maf: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/relatedness.md` and regenerate.
