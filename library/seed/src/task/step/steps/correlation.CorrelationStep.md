<!-- operon:generated -->
# Correlation

## Purpose

> Pairwise correlation matrix along one axis of a form.
>
> For every pair of positions along ``dim``, computes the correlation
> of their values across the other axes. The output is a square form
> with the same labels on both axes.
>
> This is the natural companion of ``distance_matrix``. Where
> ``distance_matrix`` measures dissimilarity, this measures
> similarity. Both are useful for sample QC, feature clustering,
> co-expression analysis, and as input to a heatmap.
>
> Output dims
> -----------
>     dims = [dim, f"{dim}_b"]
>
> Both axes carry the same labels, in the same order. ``form.data[i, j]``
> is the correlation between position ``i`` and position ``j``.
>
> Metrics
> -------
>     pearson       Pearson product-moment correlation (default)
>     spearman      Spearman rank correlation
>     kendall       Kendall's tau
>     cosine        cosine similarity (dot product of normalized rows)
>     jaccard       Jaccard similarity on binarized (>0) values
>     overlap       overlap coefficient |A and B| / min(|A|, |B|),
>                   on binarized (>0) values
>
> Missing values
> --------------
> Missing cells are handled pairwise: for each pair (i, j), only
> positions where both i and j are valid contribute to the
> correlation. This matches the standard treatment of missing data in
> correlation matrices.
>
> Size guard
> ----------
> The output is a dense ``n x n`` matrix. The memory planner accounts for its
> quadratic allocation. An optional ``max_positions`` adds a count limit;
> the default is None, leaving admission to the configured memory budget.
>
> Params:
>     dim            : axis to compute correlations along (required)
>     metric         : metric name (default "pearson")
>     min_valid      : minimum number of valid positions per pair
>                      (default 3)
>     max_positions  : refuse if dim has more positions than this
>                      (default None; governed by the memory budget)
>     output         : context key for the result (default: step name)
>
> Pairwise correlation matrix along one axis.

## Inputs and outputs

Kind: `operator`. Operator ID: `correlation`.
Input count: `1`.
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

Implementation: `src/task/step/steps/correlation.py` (`CorrelationStep`).
