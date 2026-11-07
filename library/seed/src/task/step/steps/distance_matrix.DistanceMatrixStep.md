<!-- operon:generated -->
# Distance matrix

## Purpose

> Pairwise distance matrix along one axis of a form.
>
> Computes the distance between every pair of positions along ``dim``,
> using the values across the other axes as features. The output is a
> square form with the same labels on both axes.
>
> Output dims
> -----------
>     dims = [dim, f"{dim}_b"]
>
> Both axes carry the same labels, in the same order. ``form.data[i, j]``
> is the distance between position ``i`` and position ``j``.
>
> Metrics
> -------
>     euclidean     L2 distance
>     manhattan     L1 distance
>     cosine        1 - cosine similarity
>     correlation   1 - Pearson correlation
>     braycurtis    sum(|a - b|) / sum(a + b)
>     jaccard       1 - |A and B| / |A or B|, on binarized (>0) values
>     hamming       fraction of positions where a != b, after
>                   binarization
>
> Missing values
> --------------
> Missing cells are filled with 0 before the computation. This is the
> correct interpretation for abundance matrices (an unobserved
> species has zero abundance), and it also matches how ``braycurtis``
> and ``jaccard`` are normally applied.
>
> Size guard
> ----------
> The output is a dense ``n x n`` matrix. The memory planner reserves its
> quadratic workspace/output before execution. An optional ``max_positions``
> adds a user-selected count limit; no fixed count cap is imposed by default.
>
> Params:
>     dim            : axis to compute distances along (required)
>     metric         : metric name (default "euclidean")
>     max_positions  : refuse if dim has more positions than this
>                      (default None; governed by the memory budget)
>     output         : context key for the result (default: step name)
>
> Pairwise distance matrix along one axis.

## Inputs and outputs

Kind: `operator`. Operator ID: `distance_matrix`.
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

Implementation: `src/task/step/steps/distance_matrix.py` (`DistanceMatrixStep`).
