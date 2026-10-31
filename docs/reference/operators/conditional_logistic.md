# conditional_logistic

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/conditional_logistic.py`](../../../src/task/step/steps/conditional_logistic.py)
- Tests: [`tests/test_conditional_logistic.py`](../../../tests/test_conditional_logistic.py), [`tests/test_r_oracles82.py`](../../../tests/test_r_oracles82.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `stratum_label` | Stratum Label | string |  |  |  | yes | basic |
| `outcome_label` | Outcome Label | string |  |  |  | yes | basic |
| `covariates` | 协变量 | array |  |  |  | yes | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
| `max_iter` | Max Iter | integer | 100 | 10 |  |  | basic |
| `tol` | Tol | number | 1e-08 |  | 0.001 |  | basic |
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
Fit a conditional logistic model for matched case-control strata.

--- module documentation ---

Conditional logistic regression for matched case-control data.

The conditional likelihood removes one intercept per stratum, so only
within-stratum contrasts of the covariates are used.  The implementation
uses Newton-Raphson on the exact conditional likelihood and the observed
information for standard errors.

Output form
-----------
    dims    = ["term", "statistic"]
    labels  = {term: {covariate: i},
               statistic: {"coef": 0, "se": 1, "z": 2, "P": 3,
                           "CI_low": 4, "CI_high": 5, "OR": 6}}

Params:
    stratum_label : column identifying matched sets (required)
    outcome_label : binary case/control column (required)
    covariates    : non-empty list of numeric covariate columns
    confidence    : confidence level for coefficient intervals (default .95)
    max_iter      : maximum Newton iterations (default 100)
    tol           : convergence tolerance on the Newton step (default 1e-8)
    output        : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: conditional_logistic
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    stratum_label: <string>
    outcome_label: <string>
    covariates: <array>
    confidence: <number>
    max_iter: <integer>
    tol: <number>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/conditional_logistic.md` and regenerate.
