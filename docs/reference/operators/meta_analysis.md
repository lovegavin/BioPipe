# meta_analysis

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/meta_analysis.py`](../../../src/task/step/steps/meta_analysis.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py), [`tests/test_r_oracles.py`](../../../tests/test_r_oracles.py)
- Demo tasks: none found
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `variant_dim` | Variant Dim | string | variant |  |  |  | basic |
| `study_dim` | Study Dim | string | study |  |  |  | basic |
| `method` | 方法 | string; enum=['fixed', 'random'] | random |  |  |  | basic |
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
        "param": "variant_dim",
        "default": "variant"
      },
      {
        "param": "study_dim",
        "default": "study"
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
        "param": "study_dim",
        "default": "study"
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
Abstract step.

Subclasses declare:

* ``name`` — matched against the manifest's ``name`` field.
* ``inputs_arity`` — number of input forms, or ``"*"`` for any.
* ``outputs`` — context keys the step registers on exit.

And implement ``run``. They may also implement ``export`` to
return a JSON-serializable dict of the step's full results.

--- module documentation ---

Fixed/random-effect meta-analysis of per-study effect sizes.

Inputs are two aligned matrices:

    effects : [variant, study] effect estimates (e.g. beta/logOR)
    stds    : [variant, study] standard errors

For each variant, fixed-effect inverse-variance pooling and the
DerSimonian-Laird random-effects estimator are computed. Cochran's Q
and I^2 (percentage, 0-100) are reported. A single study is allowed;
Q and I^2 are undefined and reported as NaN.
```

## Minimal YAML skeleton

```yaml
- name: meta_analysis
  inputs: [<input1>, <input2>]
  params:
    variant_dim: <string>
    study_dim: <string>
    method: <string; enum=['fixed', 'random']>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/meta_analysis.md` and regenerate.
