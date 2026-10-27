# ancom_bc

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/ancom_bc.py`](../../../src/task/step/steps/ancom_bc.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `taxon_dim` | Taxon Dim | string | taxon |  |  |  | basic |
| `group_label` | 分组字段 | string |  |  |  | yes | basic |
| `group_a` | A 组 | string / number |  |  |  | yes | basic |
| `group_b` | B 组 | string / number |  |  |  | yes | basic |
| `pseudocount` | 伪计数 | number | 1.0 |  |  |  | basic |
| `correction` | Correction | string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by'] | fdr |  |  |  | basic |
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
        "param": "taxon_dim",
        "default": "taxon"
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
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_any": [
      {
        "param": "group_label",
        "default": null
      }
    ]
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
Abstract step.

Subclasses declare:

* ``name`` — matched against the manifest's ``name`` field.
* ``inputs_arity`` — number of input forms, or ``"*"`` for any.
* ``outputs`` — context keys the step registers on exit.

And implement ``run``. They may also implement ``export`` to
return a JSON-serializable dict of the step's full results.

--- module documentation ---

Log-ratio differential abundance with sample-bias removal.

This implements the core contrast used by ANCOM-BC-style analyses:
log-counts are centred per sample (removing sample-specific bias),
the group contrast is estimated, and a Welch test plus BH correction
is reported. It is an independent Python implementation, not a direct
R ANCOMBC wrapper; structural-zero estimation and the full ANCOM-BC
mixed model are intentionally not claimed.
```

## Minimal YAML skeleton

```yaml
- name: ancom_bc
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    taxon_dim: <string>
    group_label: <string>
    group_a: <string / number>
    group_b: <string / number>
    pseudocount: <number>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/ancom_bc.md` and regenerate.
