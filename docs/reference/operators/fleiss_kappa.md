# fleiss_kappa

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/fleiss_kappa.py`](../../../src/task/step/steps/fleiss_kappa.py)
- Tests: [`tests/test_extension13.py`](../../../tests/test_extension13.py)
- Demo tasks: none found
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `subject_dim` | Subject Dim | string | subject |  |  |  | basic |
| `category_dim` | Category Dim | string | category |  |  |  | basic |
| `method` | 方法 | string; enum=['fleiss', 'randolph'] | fleiss |  |  |  | basic |
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
        "param": "subject_dim",
        "default": "subject"
      },
      {
        "param": "category_dim",
        "default": "category"
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
Fleiss' kappa for several raters on a subject x category count table.
```

## Minimal YAML skeleton

```yaml
- name: fleiss_kappa
  inputs: [<input1>]
  params:
    subject_dim: <string>
    category_dim: <string>
    method: <string; enum=['fleiss', 'randolph']>
    output: <string>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/fleiss_kappa.md` and regenerate.
