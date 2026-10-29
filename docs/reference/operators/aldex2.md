# aldex2

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/aldex2.py`](../../../src/task/step/steps/aldex2.py)
- Tests: [`tests/test_extension_operators.py`](../../../tests/test_extension_operators.py), [`tests/test_r_oracles.py`](../../../tests/test_r_oracles.py)
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
| `n_mc` | N Mc | integer | 128 | 8 |  |  | basic |
| `seed` | Seed | integer | 0 |  |  |  | basic |
| `pseudocount` | 伪计数 | number | 0.5 |  |  |  | basic |
| `monte_carlo` | Monte Carlo | boolean | True |  |  |  | basic |
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

Compositional differential abundance (ALDEx-style Monte Carlo CLR test).

This follows the ALDEx2 idea: counts are converted to a probability
vector with a Dirichlet/Gamma Monte Carlo, log-ratio transformed, and a
Welch t-test is applied per taxon. The p-values are averaged over
Monte Carlo instances and BH-corrected.

It is an independent implementation, not a byte-for-byte R ALDEx2
wrapper. The R package's exact Monte Carlo and effect-size conventions
are recorded in the test notes; outputs are labelled explicitly.
```

## Minimal YAML skeleton

```yaml
- name: aldex2
  inputs: [<input1>, <input2>]
  params:
    sample_dim: <string>
    taxon_dim: <string>
    group_label: <string>
    group_a: <string / number>
    group_b: <string / number>
    n_mc: <integer>
    seed: <integer>
    pseudocount: <number>
    monte_carlo: <boolean>
    correction: <string; enum=['fdr', 'bonferroni', 'holm', 'hommel', 'fdr_by']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/aldex2.md` and regenerate.
