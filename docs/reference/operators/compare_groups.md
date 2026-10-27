# compare_groups

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-expression`
- Source: [`src/task/step/steps/compare_groups.py`](../../../src/task/step/steps/compare_groups.py)
- Tests: [`tasks/compare_groups_demo/test_compare_groups.py`](../../../tasks/compare_groups_demo/test_compare_groups.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py)
- Demo tasks: [`tasks/compare_groups_demo/task.yaml`](../../../tasks/compare_groups_demo/task.yaml), [`tasks/ma_plot_demo/task.yaml`](../../../tasks/ma_plot_demo/task.yaml), [`tasks/proteomics_de_demo/task.yaml`](../../../tasks/proteomics_de_demo/task.yaml), [`tasks/rnaseq_de_demo/task.yaml`](../../../tasks/rnaseq_de_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/volcano_demo/task.yaml`](../../../tasks/volcano_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `group_dim` | 分析维度 | string |  |  |  | yes | basic |
| `group_label` | 分析维度 | string |  |  |  | yes | basic |
| `mode` | 模式 | string; enum=['two_groups', 'one_vs_rest', 'pairwise'] | two_groups |  |  |  | basic |
| `group_a` | A 组 | string / number |  |  |  |  | basic |
| `group_b` | B 组 | string / number |  |  |  |  | basic |
| `groups` | 分组顺序 | array |  |  |  |  | basic |
| `min_per_group` | 每组最少样本 | integer | 2 | 1 |  |  | basic |
| `method` | 方法 | string; enum=['ttest', 'welch', 'mannwhitney', 'wilcoxon', 'deseq2'] | ttest |  |  |  | basic |

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
      },
      {
        "param": "group_dim",
        "default": null
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
        "param": "group_dim",
        "default": null
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
  "mode": "compare_groups"
}
```

## Processing rules (source docstring)

```text
Compare groups along one dimension.

--- module documentation ---

Compare groups along one dimension of a 2D form.

Three modes
-----------
    two_groups     compare group_a vs group_b (default, backward
                   compatible with the original two-group API).
                   Output dims: [dim, "statistic"].
    one_vs_rest    for every group g: g vs the union of all other
                   groups. Output dims: [dim, "comparison",
                   "statistic"], with one entry per group.
    pairwise       every unordered pair (g_i, g_j). Output dims:
                   [dim, "comparison", "statistic"].

Methods
-------
    ttest        scipy.stats.ttest_ind(equal_var=True)
    welch        scipy.stats.ttest_ind(equal_var=False)
    mannwhitney  scipy.stats.mannwhitneyu
    deseq2       pydeseq2 negative binomial GLM

The two-group output is a 2D form with columns log2FC, mean_a,
mean_b, stat, P, N. The multi-group output adds a "comparison"
axis between the feature axis and the statistic axis.

Consuming a multi-group result in a 2D pipeline requires selecting
one comparison first:

    - name: select
      inputs: [result]
      params: {dim: comparison, labels: ["A"], output: result_a}

Params:
    dim          : feature dim (required)
    group_dim    : sample dim shared by both inputs (required)
    group_label  : column on the metadata's other dim (required)
    mode         : "two_groups" | "one_vs_rest" | "pairwise"
                   (default "two_groups")
    group_a      : first group (required for two_groups)
    group_b      : second group (required for two_groups)
    groups       : list of group names to compare in multi-group
                   modes (optional; if omitted, all groups present
                   in the metadata are used)
    method       : "ttest" | "welch" | "mannwhitney" | "deseq2"
                   (default "ttest")
    min_per_group: skip a comparison if either side has fewer than
                   this many samples (multi-group only, default 2)
    output       : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: compare_groups
  inputs: [<input1>, <input2>]
  params:
    dim: <string>
    group_dim: <string>
    group_label: <string>
    mode: <string; enum=['two_groups', 'one_vs_rest', 'pairwise']>
    group_a: <string / number>
    group_b: <string / number>
    groups: <array>
    min_per_group: <integer>
    method: <string; enum=['ttest', 'welch', 'mannwhitney', 'wilcoxon', 'deseq2']>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/compare_groups.md` and regenerate.
