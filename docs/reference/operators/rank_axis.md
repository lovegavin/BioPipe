# rank_axis

> Auto-generated reference. Verify edge cases against the linked source and tests before publishing an analysis.

- Package: `biopipe-core`
- Source: [`src/task/step/steps/rank_axis.py`](../../../src/task/step/steps/rank_axis.py)
- Tests: [`tasks/rank_axis_demo/test_rank_axis.py`](../../../tasks/rank_axis_demo/test_rank_axis.py), [`tasks/single_cell_route_demo/test_single_cell_route.py`](../../../tasks/single_cell_route_demo/test_single_cell_route.py), [`tasks/verify_existing_operators.py`](../../../tasks/verify_existing_operators.py), [`tasks/verify_multi_omics.py`](../../../tasks/verify_multi_omics.py), [`tasks/verify_single_cell.py`](../../../tasks/verify_single_cell.py)
- Demo tasks: [`tasks/cluster_axis_demo/task.yaml`](../../../tasks/cluster_axis_demo/task.yaml), [`tasks/dotplot_demo/task.yaml`](../../../tasks/dotplot_demo/task.yaml), [`tasks/enrich_go_demo/task.yaml`](../../../tasks/enrich_go_demo/task.yaml), [`tasks/enrichment_plot_demo/task.yaml`](../../../tasks/enrichment_plot_demo/task.yaml), [`tasks/multi_omics_route_demo/task.yaml`](../../../tasks/multi_omics_route_demo/task.yaml), [`tasks/rank_axis_demo/task.yaml`](../../../tasks/rank_axis_demo/task.yaml), [`tasks/reduce_demo/task.yaml`](../../../tasks/reduce_demo/task.yaml), [`tasks/scrnaseq_demo/task.yaml`](../../../tasks/scrnaseq_demo/task.yaml), [`tasks/single_cell_demo/task.yaml`](../../../tasks/single_cell_demo/task.yaml), [`tasks/single_cell_route_demo/task.yaml`](../../../tasks/single_cell_route_demo/task.yaml), [`tasks/violin_demo/task.yaml`](../../../tasks/violin_demo/task.yaml)
- Inputs arity: `1`; output parameter: `output`

## Parameters

| key | title | type | default | min | max | required | group |
|---|---|---|---|---|---|---|---|
| `dim` | 分析维度 | string |  |  |  | yes | basic |
| `by` | 排序依据 | string; enum=['variance', 'std', 'mean', 'sum', 'nonzero', 'abs_mean', 'max'] |  |  |  | yes | basic |
| `top_n` | 保留数量 | integer |  | 1 |  |  | basic |
| `min_value` | 最小值 | number |  |  |  |  | basic |
| `keep_ties` | 保留并列 | boolean | False |  |  |  | basic |
| `descending` | 降序 | boolean | True |  |  |  | basic |

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
  "mode": "subset"
}
```

## Processing rules (source docstring)

```text
Rank positions along one axis by a statistic.

--- module documentation ---

Rank positions along one axis by a statistic and keep the top N.

For each position along ``dim``, computes a ranking statistic over
the other axes, then returns a subset of the input form containing
only the selected positions.

Selection
---------
``top_n``      keep the N highest-ranked positions
``min_value``  keep positions whose statistic is >= the threshold
               (or <= when ``descending=False``)

When both are given, the selection is their **intersection**: a
position must be in the top N **and** satisfy the threshold.

Ranking statistics
------------------
    variance     variance across the other axes
    std          standard deviation
    mean         mean across the other axes
    sum          sum across the other axes
    nonzero      number of non-zero values
    abs_mean     mean of absolute values
    max          maximum value

Missing cells are excluded from every statistic.

Ties
----
When several positions share the same statistic value, they are
ordered by their original label order. If ``keep_ties`` is True and
a tie straddles the top-N cutoff, all tied positions are kept and
the result may exceed ``top_n``. If False (default), exactly
``top_n`` positions are kept.

Params:
    dim         : dimension to rank (required)
    by          : statistic name (required)
    top_n       : how many positions to keep
    min_value   : threshold on the statistic
    keep_ties   : keep all tied positions at the top-N cutoff
                  (default False)
    descending  : rank from largest to smallest (default True)
    output      : context key for the result (default: step name)

At least one of ``top_n`` or ``min_value`` is required.
```

## Minimal YAML skeleton

```yaml
- name: rank_axis
  inputs: [<input1>]
  params:
    dim: <string>
    by: <string; enum=['variance', 'std', 'mean', 'sum', 'nonzero', 'abs_mean', 'max']>
    top_n: <integer>
    min_value: <number>
    keep_ties: <boolean>
    descending: <boolean>
    output: <output_name>
```

The skeleton is a parameter checklist, not a runnable example; use a demo task or ask the LLM to fill values from inspected data.

## Before using this operator

This page is generated from the declaration. If the analysis depends on a numerical edge case, read the linked source and at least one linked test. If the page lacks a caveat you need, add it to `docs/reference/notes/operators/rank_axis.md` and regenerate.
