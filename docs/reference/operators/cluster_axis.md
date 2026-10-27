# cluster_axis

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/cluster_axis.py`](../../../src/task/step/steps/cluster_axis.py)
- Tests: [`tasks/cluster_axis_demo/test_cluster_axis.py`](../../../tasks/cluster_axis_demo/test_cluster_axis.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py), [`tasks/verify_stats_operators.py`](../../../tasks/verify_stats_operators.py)
- Demo tasks: [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `method` | 方法 | string; enum=['kmeans', 'hierarchical', 'louvain'] |  |  |  | yes | basic |
| `n_clusters` | 聚类数 | integer |  | 1 |  |  | basic |
| `n_neighbors` | 邻居数 | integer | 15 | 1 |  |  | advanced |
| `resolution` | 分辨率 | number | 1.0 |  |  |  | basic |
| `random_state` | 随机种子 | integer | 0 |  |  |  | advanced |

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
      "const": "clusters"
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
      "name": "cluster",
      "labels": [
        "cluster"
      ]
    }
  ]
}
```

## Processing rules (source docstring)

```text
Cluster positions along one axis.

--- module documentation ---

Cluster positions along one axis of a form.

Groups positions along ``dim`` into clusters, using the values
across the other axes as features. The output is a new 2D form:

    dims = [dim, "cluster"]
    data: one integer cluster id per position

Cluster ids are renumbered 0..n-1 in order of first appearance in
the original label order.

Methods
-------
    kmeans         KMeans (scikit-learn). Requires ``n_clusters``.
    hierarchical   Ward hierarchical clustering (scipy). Requires
                   ``n_clusters``.
    louvain        Louvain community detection on a KNN graph
                   (networkx + scikit-learn). Requires
                   ``n_neighbors``; ``resolution`` tunes cluster
                   granularity.

Missing values are filled with the feature mean before clustering.

Params:
    dim            : dimension to cluster along (required)
    method         : "kmeans" | "hierarchical" | "louvain" (required)
    n_clusters     : number of clusters (kmeans, hierarchical)
    n_neighbors    : KNN size for louvain (default 15)
    resolution     : Louvain resolution (default 1.0)
    random_state   : random seed for kmeans / louvain (default 0)
    output         : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: cluster_axis
  inputs: [<input1>]
  params:
    dim: <string>
    method: <string; enum=['kmeans', 'hierarchical', 'louvain']>
    n_clusters: <integer>
    n_neighbors: <integer>
    resolution: <number>
    random_state: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/cluster_axis.md` and regenerate.
