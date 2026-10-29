# correction

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/correction.py`](../../../src/task/step/steps/correction.py)
- Tests: [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py)
- Demo tasks: [`tasks/correction_demo/task.yaml`](../../../tasks/correction_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `alpha` | 显著性水平 | number | 0.05 | 0 | 1 |  | advanced |
| `dim` | 统计量维度 | string | statistic |  |  |  | basic |
| `method` | 校正方法 | any; enum=['fdr', 'bonferroni'] | bonferroni |  |  |  | basic |
| `pfield` | P 值标签 | string | P |  |  |  | basic |

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
        "default": "statistic"
      }
    ],
    "labels": [
      {
        "dim": {
          "param": "dim",
          "default": "statistic"
        },
        "values": {
          "param": "pfield",
          "default": "P"
        }
      }
    ],
    "parallel": [],
    "ndim": 2,
    "values": "pvalue"
  }
]
```

## Output contract

```json
{
  "mode": "correction"
}
```

## Processing rules (source docstring)

```text
Multiple-testing correction on a result table.

    Params:
        method : "bonferroni" or "fdr"
        alpha  : significance level (default 0.05)
        pfield : name of the p-value column (default "P")
        dim    : dimension carrying the statistic labels (default
                 "statistic")
        output : context key for the result

--- module documentation ---

Multiple-testing correction.
```

## Minimal YAML skeleton

```yaml
- name: correction
  inputs: [<input1>]
  params:
    alpha: <number>
    dim: <string>
    method: <any; enum=['fdr', 'bonferroni']>
    pfield: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/correction.md` and regenerate.
