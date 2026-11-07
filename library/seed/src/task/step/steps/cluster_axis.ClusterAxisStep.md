<!-- operon:generated -->
# Clustering

## Purpose

> Cluster positions along one axis of a form.
>
> Groups positions along ``dim`` into clusters, using the values
> across the other axes as features. The output is a new 2D form:
>
>     dims = [dim, "cluster"]
>     data: one integer cluster id per position
>
> Cluster ids are renumbered 0..n-1 in order of first appearance in
> the original label order.
>
> Methods
> -------
>     kmeans         KMeans (scikit-learn). Requires ``n_clusters``.
>     hierarchical   Ward hierarchical clustering (scipy). Requires
>                    ``n_clusters``.
>     louvain        Louvain community detection on a KNN graph
>                    (networkx + scikit-learn). Requires
>                    ``n_neighbors``; ``resolution`` tunes cluster
>                    granularity.
>
> Missing values are filled with the feature mean before clustering.
>
> Params:
>     dim            : dimension to cluster along (required)
>     method         : "kmeans" | "hierarchical" | "louvain" (required)
>     n_clusters     : number of clusters (kmeans, hierarchical)
>     n_neighbors    : KNN size for louvain (default 15)
>     resolution     : Louvain resolution (default 1.0)
>     random_state   : random seed for kmeans / louvain (default 0)
>     output         : context key for the result (default: step name)
>
> Cluster positions along one axis.

## Inputs and outputs

Kind: `operator`. Operator ID: `cluster_axis`.
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

Implementation: `src/task/step/steps/cluster_axis.py` (`ClusterAxisStep`).
