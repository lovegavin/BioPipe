# diversity

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/diversity.py`](../../../src/task/step/steps/diversity.py)
- Tests: [`tasks/diversity_demo/test_diversity.py`](../../../tasks/diversity_demo/test_diversity.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py)
- Demo tasks: [`tasks/bin_demo/task.yaml`](../../../tasks/bin_demo/task.yaml), [`tasks/diversity_demo/task.yaml`](../../../tasks/diversity_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `metrics` | 指标 | any |  |  |  | yes | basic |

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
    "labels": [],
    "parallel": []
  }
]
```

## Output contract

```json
{
  "mode": "project",
  "derived": true,
  "info": {
    "missing_code": {
      "type": [
        "number",
        "null"
      ]
    },
    "representation": {
      "type": "string",
      "const": "diversity"
    }
  },
  "drop_dims": [
    {
      "param": "dim",
      "default": null
    }
  ],
  "append_dims": [
    {
      "name": "metric",
      "labels": {
        "param": "metrics",
        "default": null
      }
    }
  ]
}
```

## Processing rules (source docstring)

```text
Compute diversity metrics along one axis.

--- module documentation ---

Diversity metrics along one axis of a form.

Reduce ``dim`` into one or more diversity metrics, preserving every other
axis. The output replaces the reduced axis with a final ``metric`` axis.

Metrics
-------
    shannon        Shannon entropy H = -sum(p_i * log(p_i))
    simpson        Gini-Simpson index 1 - sum(p_i^2)
    richness       number of non-zero values
    evenness       Shannon / log(richness)
    gini           Gini coefficient of the distribution

Where p_i = v_i / sum(v) is the relative abundance of the i-th
position along the other axis. Non-finite values are dropped before
computing p; a position whose total is zero yields NaN for every
metric that requires proportions.

Axis-parallel info on the reduced dim is dropped from the output.
Info for surviving dims passes through. ``info["encoders"]`` is
trimmed to surviving dims.

Params:
    dim      : dimension to compute metrics along (required)
    metrics  : metric name, or list of names (required)
    output   : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: diversity
  inputs: [<input1>]
  params:
    dim: <string>
    metrics: <any>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/diversity.md` and regenerate.
