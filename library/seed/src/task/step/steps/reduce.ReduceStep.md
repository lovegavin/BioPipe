<!-- operon:generated -->
# PCA / PCoA / UMAP / t-SNE

## Purpose

> Dimensionality reduction along one axis of a form.
>
> Compresses one axis of a 2D form into a small number of components.
> The other axis becomes the observation axis of the output.
>
> Two kinds of input
> ------------------
> 1. Feature matrix ``[feature, sample]`` (or the reverse). The
>    operator compresses the feature axis into components. Methods:
>    ``pca``, ``umap``, ``tsne``.
>
> 2. Square distance matrix ``[sample, sample_b]`` (produced by
>    ``distance_matrix``). The operator computes principal coordinates
>    of the distance matrix. Method: ``pcoa``.
>
> The output always has the form::
>
>     dims = [<observation_dim>, "component"]
>
> Output component labels
> -----------------------
>     pca   -> "PC1", "PC2", ...
>     pcoa  -> "PCo1", "PCo2", ...
>     umap  -> "UMAP1", "UMAP2", ...
>     tsne  -> "tSNE1", "tSNE2", ...
>
> Standardization
> ---------------
> For ``pca`` / ``umap`` / ``tsne``, ``standardize=True`` (default)
> divides each feature by its standard deviation after centering.
> For ``pcoa``, standardization does not apply and is ignored.
>
> Missing values
> --------------
> Feature matrix: missing cells are filled with the feature mean
> before any standardization.
> Distance matrix: missing cells are treated as 0, and the double
> centering handles the rest.
>
> Params:
>     dim            : dim to compress, or the first axis of a
>                      distance matrix (required)
>     method         : "pca" | "umap" | "tsne" | "pcoa"
>                      (default "pca")
>     n_components   : number of components to keep
>                      (pca=10, umap=2, tsne=2, pcoa=10)
>     standardize    : z-score features before reducing, only for
>                      pca / umap / tsne (default True)
>     random_state   : random seed for umap / tsne (default 0)
>     output         : context key for the result (default: step name)
>
> Method-specific parameters are forwarded as-is:
>     umap: n_neighbors, min_dist, metric
>     tsne: perplexity, learning_rate, n_iter
>
> Reduce one axis of a 2D form to a small number of components.

## Inputs and outputs

Kind: `operator`. Operator ID: `reduce`.
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

Implementation: `src/task/step/steps/reduce.py` (`ReduceStep`).
