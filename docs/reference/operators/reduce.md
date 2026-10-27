# reduce

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/reduce.py`](../../../src/task/step/steps/reduce.py)
- Tests: [`tasks/reduce_demo/test_reduce.py`](../../../tasks/reduce_demo/test_reduce.py), [`tasks/reduce_pcoa_demo/test_reduce_pcoa.py`](../../../tasks/reduce_pcoa_demo/test_reduce_pcoa.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tasks/verify_stats_operators.py`](../../../tasks/verify_stats_operators.py)
- Demo tasks: [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/join_demo/task.yaml`](../../../tasks/join_demo/task.yaml), [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/multi_omics_route_demo/task.yaml`](../../../tasks/multi_omics_route_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/reduce_pcoa_demo/task.yaml`](../../../tasks/reduce_pcoa_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `method` | 方法 | string; enum=['pca', 'pcoa', 'umap', 'tsne'] | pca |  |  |  | basic |
| `n_components` | 主成分数 | integer |  | 1 |  |  | basic |
| `standardize` | 标准化 | boolean | True |  |  |  | basic |
| `random_state` | 随机种子 | integer | 0 |  |  |  | advanced |
| `n_neighbors` | 邻居数 | integer |  | 2 |  |  | advanced |
| `min_dist` | Min Dist | number |  | 0 |  |  | advanced |
| `metric` | 距离/相关指标 | string |  |  |  |  | advanced |
| `perplexity` | Perplexity | number |  |  |  |  | advanced |
| `learning_rate` | 学习率 | any |  |  |  |  | advanced |
| `n_iter` | 迭代次数 | integer |  | 250 |  |  | advanced |

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
    "parallel": [],
    "ndim": 2
  }
]
```

## Output contract

```json
{
  "mode": "choose",
  "param": "method",
  "default": "pca",
  "cases": {
    "pcoa": {
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
          "const": "scores"
        }
      },
      "keep_dims": [
        {
          "param": "dim",
          "default": null
        }
      ],
      "append_dims": [
        {
          "name": "component"
        }
      ]
    }
  },
  "otherwise": {
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
        "const": "scores"
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
        "name": "component"
      }
    ]
  }
}
```

## Processing rules (source docstring)

```text
Reduce one axis of a 2D form to a small number of components.

--- module documentation ---

Dimensionality reduction along one axis of a form.

Compresses one axis of a 2D form into a small number of components.
The other axis becomes the observation axis of the output.

Two kinds of input
------------------
1. Feature matrix ``[feature, sample]`` (or the reverse). The
   operator compresses the feature axis into components. Methods:
   ``pca``, ``umap``, ``tsne``.

2. Square distance matrix ``[sample, sample_b]`` (produced by
   ``distance_matrix``). The operator computes principal coordinates
   of the distance matrix. Method: ``pcoa``.

The output always has the form::

    dims = [<observation_dim>, "component"]

Output component labels
-----------------------
    pca   -> "PC1", "PC2", ...
    pcoa  -> "PCo1", "PCo2", ...
    umap  -> "UMAP1", "UMAP2", ...
    tsne  -> "tSNE1", "tSNE2", ...

Standardization
---------------
For ``pca`` / ``umap`` / ``tsne``, ``standardize=True`` (default)
divides each feature by its standard deviation after centering.
For ``pcoa``, standardization does not apply and is ignored.

Missing values
--------------
Feature matrix: missing cells are filled with the feature mean
before any standardization.
Distance matrix: missing cells are treated as 0, and the double
centering handles the rest.

Params:
    dim            : dim to compress, or the first axis of a
                     distance matrix (required)
    method         : "pca" | "umap" | "tsne" | "pcoa"
                     (default "pca")
    n_components   : number of components to keep
                     (pca=10, umap=2, tsne=2, pcoa=10)
    standardize    : z-score features before reducing, only for
                     pca / umap / tsne (default True)
    random_state   : random seed for umap / tsne (default 0)
    output         : context key for the result (default: step name)

Method-specific parameters are forwarded as-is:
    umap: n_neighbors, min_dist, metric
    tsne: perplexity, learning_rate, n_iter
```

## Minimal YAML skeleton

```yaml
- name: reduce
  inputs: [<input1>]
  params:
    dim: <string>
    method: <string; enum=['pca', 'pcoa', 'umap', 'tsne']>
    n_components: <integer>
    standardize: <boolean>
    random_state: <integer>
    n_neighbors: <integer>
    min_dist: <number>
    metric: <string>
    perplexity: <number>
    learning_rate: <any>
    n_iter: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/reduce.md` and regenerate.
