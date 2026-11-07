<!-- operon:generated -->
# Group comparison

## Purpose

> Compare groups along one dimension of a 2D form.
>
> Three modes
> -----------
>     two_groups     compare group_a vs group_b (default, backward
>                    compatible with the original two-group API).
>                    Output dims: [dim, "statistic"].
>     one_vs_rest    for every group g: g vs the union of all other
>                    groups. Output dims: [dim, "comparison",
>                    "statistic"], with one entry per group.
>     pairwise       every unordered pair (g_i, g_j). Output dims:
>                    [dim, "comparison", "statistic"].
>
> Methods
> -------
>     ttest        scipy.stats.ttest_ind(equal_var=True)
>     welch        scipy.stats.ttest_ind(equal_var=False)
>     mannwhitney  scipy.stats.mannwhitneyu
>     deseq2       pydeseq2 negative binomial GLM
>
> The two-group output is a 2D form with columns log2FC, mean_a,
> mean_b, stat, P, N. The multi-group output adds a "comparison"
> axis between the feature axis and the statistic axis.
>
> Consuming a multi-group result in a 2D pipeline requires selecting
> one comparison first:
>
>     - name: select
>       inputs: [result]
>       params: {dim: comparison, labels: ["A"], output: result_a}
>
> Params:
>     dim          : feature dim (required)
>     group_dim    : sample dim shared by both inputs (required)
>     group_label  : column on the metadata's other dim (required)
>     mode         : "two_groups" | "one_vs_rest" | "pairwise"
>                    (default "two_groups")
>     group_a      : first group (required for two_groups)
>     group_b      : second group (required for two_groups)
>     groups       : list of group names to compare in multi-group
>                    modes (optional; if omitted, all groups present
>                    in the metadata are used)
>     method       : "ttest" | "welch" | "mannwhitney" | "deseq2"
>                    (default "ttest")
>     min_per_group: skip a comparison if either side has fewer than
>                    this many samples (multi-group only, default 2)
>     output       : context key for the result (default: step name)
>
> Compare groups along one dimension.

## Inputs and outputs

Kind: `operator`. Operator ID: `compare_groups`.
Input count: `2`.
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

Runs in the shared Operon interpreter.

## Limitations

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/task/step/steps/compare_groups.py` (`CompareGroupsStep`).
