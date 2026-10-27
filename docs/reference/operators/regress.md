# regress

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/regress.py`](../../../src/task/step/steps/regress.py)
- Tests: [`tasks/verify_genetics_operators.py`](../../../tasks/verify_genetics_operators.py)
- Demo tasks: [`tasks/correction_demo/task.yaml`](../../../tasks/correction_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/regress_demo/task.yaml`](../../../tasks/regress_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `covariates` | 协变量标签 | array | [] |  |  |  | basic |
| `dim` | 特征维度 | string |  |  |  | yes | basic |
| `method` | 模型 | any; enum=['auto', 'ols', 'logit'] | auto |  |  |  | basic |
| `response` | 响应变量标签 | string |  |  |  | yes | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {},
    "dims": [
      {
        "param": "dim",
        "default": null
      }
    ],
    "labels": [
      {
        "dim": {
          "param": "dim",
          "default": null
        },
        "values": {
          "param": "response",
          "default": null
        }
      },
      {
        "dim": {
          "param": "dim",
          "default": null
        },
        "values": {
          "param": "covariates",
          "default": []
        }
      }
    ],
    "parallel": [],
    "ndim": 2
  }
]
```

## Output contract

```json
{
  "mode": "regress"
}
```

## Processing rules (source docstring)

```text
Regression of a response on each predictor, adjusting for covariates.

Params:
    dim        : dimension to iterate over
    response   : label of the response column
    covariates : labels of covariates (optional)
    method     : "ols" | "logit" | "auto" (default)
    output     : context key for the result

--- module documentation ---

Multiple regression over one dimension of a wide form.

Input is a single wide form. One position along a chosen dimension is
the response; a set of other positions are covariates; all remaining
positions are tested one at a time as predictors.

For each predictor, the operator fits:

    response ~ predictor + covariates

Failure policy
--------------
A predictor is skipped, with a recorded reason, only when a known
condition prevents a meaningful fit:

* too few valid samples
* predictor is constant
* binary response has a single class in this subset
* design matrix is rank-deficient
* logistic fit hits perfect separation
* the fit returned non-finite estimates

Any other exception propagates. Nothing is silently swallowed.
```

## Minimal YAML skeleton

```yaml
- name: regress
  inputs: [<input1>]
  params:
    covariates: <array>
    dim: <string>
    method: <any; enum=['auto', 'ols', 'logit']>
    response: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/regress.md` and regenerate.
