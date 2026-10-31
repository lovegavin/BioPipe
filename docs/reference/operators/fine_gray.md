# fine_gray

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/fine_gray.py`](../../../src/task/step/steps/fine_gray.py)
- Tests: [`tests/test_extension82.py`](../../../tests/test_extension82.py), [`tests/test_r_oracles72.py`](../../../tests/test_r_oracles72.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `sample_dim` | 样本维度 | string | sample |  |  |  | basic |
| `feature_dim` | 特征维度 | string | feature |  |  |  | basic |
| `time_label` | 随访时间列 | string |  |  |  | yes | basic |
| `event_label` | 结局代码列 | string |  |  |  | yes | basic |
| `covariates` | 协变量列 | array |  |  |  | yes | basic |
| `event_code` | 目标事件代码 | integer | 1 |  |  |  | basic |
| `censor_code` | 删失代码 | integer | 0 |  |  |  | basic |
| `confidence` | Confidence | number | 0.95 |  |  |  | basic |
| `max_iter` | Max Iter | integer | 100 | 1 | 1000 |  | basic |
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
Fine-Gray subdistribution hazard regression.

--- module documentation ---

Fine-Gray subdistribution hazard regression.

The implementation follows the weighted partial-likelihood form of
Fine and Gray (1999).  At each event time the risk set contains
subjects still under observation plus subjects that already failed
from a competing cause; the latter receive the time-dependent weight
``G(t) / G(T_i)`` where ``G`` is the Kaplan-Meier estimate of the
censoring distribution.  Covariates are used without an intercept.

Output form
-----------
    dims    = ["term", "statistic"]
    labels  = {term: {name: i},
               statistic: {"coef": 0, "HR": 1, "se": 2,
                           "z": 3, "P": 4,
                           "CI_low": 5, "CI_high": 6}}

The reported standard errors use the robust sandwich estimator, matching
``cmprsk::crr`` (the ``var`` component), rather than the naive inverse
information.

Params:
    time_label   : follow-up time column (required)
    event_label  : event-code column (required)
    covariates   : non-empty list of numeric covariate columns
    event_code   : code for the event of interest (default 1)
    censor_code  : code for administrative censoring (default 0)
    confidence   : confidence level for coefficient intervals (default .95)
    max_iter     : maximum Newton iterations (default 100)
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: fine_gray
  inputs: [<input1>]
  params:
    sample_dim: <string>
    feature_dim: <string>
    time_label: <string>
    event_label: <string>
    covariates: <array>
    event_code: <integer>
    censor_code: <integer>
    confidence: <number>
    max_iter: <integer>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/fine_gray.md` and regenerate.
