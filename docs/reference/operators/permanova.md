# permanova

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-microbiome`
- Source: [`src/task/step/steps/permanova.py`](../../../src/task/step/steps/permanova.py)
- Tests: [`tasks/permanova_demo/test_permanova.py`](../../../tasks/permanova_demo/test_permanova.py), [`tasks/verify_stats_operators.py`](../../../tasks/verify_stats_operators.py)
- Demo tasks: [`tasks/microbiome_demo/task.yaml`](../../../tasks/microbiome_demo/task.yaml), [`tasks/permanova_demo/task.yaml`](../../../tasks/permanova_demo/task.yaml)
- Inputs arity: `2`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dist_dim` | 距离维度 | string | sample |  |  |  | basic |
| `group_dim` | 分组维度 | string |  |  |  |  | basic |
| `group_label` | 分组维度 | string |  |  |  | yes | basic |
| `groups` | 分组顺序 | array |  |  |  |  | basic |
| `pairwise` | 两两比较 | boolean | False |  |  |  | basic |
| `n_permutations` | 置换次数 | integer | 999 | 1 |  |  | basic |
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
        "param": "dist_dim",
        "default": "sample"
      },
      {
        "param": "dist_dim",
        "default": "sample",
        "suffix": "_b"
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
        "default": {
          "param": "dist_dim",
          "default": "sample"
        }
      }
    ],
    "labels": [],
    "parallel": [],
    "ndim": 2,
    "labels_axis": [
      {
        "axis": 1,
        "values": [
          {
            "param": "group_label",
            "default": null
          }
        ]
      }
    ]
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
    "dims": [
      "comparison",
      "statistic"
    ],
    "labels": {
      "comparison": null,
      "statistic": [
        "F",
        "R2",
        "P",
        "n_perm"
      ]
    },
    "axis_info": {},
    "info": {
      "missing_code": {
        "type": [
          "number",
          "null"
        ]
      },
      "representation": {
        "type": "string",
        "const": "permanova"
      }
    }
  }
}
```

## Processing rules (source docstring)

```text
PERMANOVA on a distance matrix with a grouping column.

--- module documentation ---

PERMANOVA — permutation-based multivariate analysis of variance.

Given a distance matrix (produced by ``distance_matrix``) and a
group label for each sample, tests whether the between-group
distances are larger than expected by chance.

Two inputs share a sample dim. The first is a square distance
matrix, the second carries the group column. Both must have the
same labels on the sample dim.

Method
------
Anderson (2001) PERMANOVA on a distance matrix:

    a_ij    = d_ij^2 / 2
    SS_T    = sum over all i,j of a_ij, divided by n
    SS_W    = sum_g (1/n_g) * sum over i,j in g of a_ij
    SS_A    = SS_T - SS_W
    F       = (SS_A / (g-1)) / (SS_W / (n-g))
    R^2     = SS_A / SS_T
    p-value = fraction of permutations with F >= F_obs

Two modes
---------
    overall     one test across all groups (default)
    pairwise    one test per unordered pair of groups, in addition
                to the overall test

Output
------
    dims    = ["comparison", "statistic"]
    labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
               statistic: {"F": 0, "R2": 1, "P": 2, "n_perm": 3}}

Params:
    dist_dim        : sample dim on the distance matrix (default
                      "sample")
    group_dim       : sample dim on the metadata form (default
                      same as dist_dim)
    group_label     : column label on the metadata's other dim
                      (required)
    groups          : optional list of group names, in order; if
                      omitted, all groups present in the metadata
                      are used
    pairwise        : run pairwise tests in addition to the overall
                      test (default False)
    n_permutations  : permutation count (default 999)
    random_state    : random seed for permutations (default 0)
    output          : context key for the result (default: step name)
```

## Minimal YAML skeleton

```yaml
- name: permanova
  inputs: [<input1>, <input2>]
  params:
    dist_dim: <string>
    group_dim: <string>
    group_label: <string>
    groups: <array>
    pairwise: <boolean>
    n_permutations: <integer>
    random_state: <integer>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/permanova.md` and regenerate.
