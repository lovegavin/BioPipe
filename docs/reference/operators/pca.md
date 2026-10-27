# pca

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-genetics`
- Source: [`src/task/step/steps/pca.py`](../../../src/task/step/steps/pca.py)
- Tests: [`tasks/bgen_qc_demo/test_bgen_qc.py`](../../../tasks/bgen_qc_demo/test_bgen_qc.py), [`tasks/multi_omics_route_demo/test_multi_omics_route.py`](../../../tasks/multi_omics_route_demo/test_multi_omics_route.py), [`tasks/verify_bgen_qc.py`](../../../tasks/verify_bgen_qc.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_multi_omics.py`](../../../tasks/verify_multi_omics.py)
- Demo tasks: [`tasks/bgen_qc_demo/task.yaml`](../../../tasks/bgen_qc_demo/task.yaml), [`tasks/gwas_demo/task.yaml`](../../../tasks/gwas_demo/task.yaml), [`tasks/pca_demo/task.yaml`](../../../tasks/pca_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/sop_demo/task.yaml`](../../../tasks/sop_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 压缩维度 | string |  |  |  | yes | basic |
| `n_components` | 主成分数量 | integer | 10 | 1 |  |  | basic |

## Input contract

```json
[
  {
    "version": 1,
    "numeric": true,
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      }
    },
    "dims": [
      {
        "param": "dim",
        "default": null
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
  "mode": "pca"
}
```

## Processing rules (source docstring)

```text
PCA along one dimension.

Params:
    dim          : dimension to compress
    n_components : number of components to keep (default 10)
    output       : context key for the result (default: step name)

--- module documentation ---

Principal component analysis.

Compresses one dimension of a 2D form into a small number of principal
components. The other dimension becomes the "observation" axis of the
output.

Missing cells are filled with the column mean before standardization.
The output retains observation annotations and declares score semantics.

Layout:
    input  : [<dim_to_compress>, <observation_dim>]  (any 2D orientation)
    output : [<observation_dim>, component]
```

## Minimal YAML skeleton

```yaml
- name: pca
  inputs: [<input1>]
  params:
    dim: <string>
    n_components: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/pca.md` and regenerate.
