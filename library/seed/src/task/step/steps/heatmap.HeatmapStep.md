<!-- operon:generated -->
# Heatmap

## Purpose

> Heatmap of a 2D form.
>
> Renders the matrix as an image with one cell per position. Rows and
> columns can be reordered by hierarchical clustering, and rows can be
> standardized before plotting.
>
> Row selection
> -------------
>     select="variance"   pick the top ``top_n`` rows by variance
>                         (default)
>     select="label"      pick the rows named in ``labels``
>     select="all"        keep all rows
>
> Standardization
> ---------------
>     standardize="row"   z-score each row (mean 0, std 1)
>     standardize="col"   z-score each column
>     standardize="none"  no transformation (default)
>
> Missing values are shown as the ``nan_color``.
>
> Params:
>     dim          : feature dim (default "feature")
>     other_dim    : sample dim (default "sample")
>     select       : "variance" | "label" | "all"
>     top_n        : number of rows when select="variance" (default 50)
>     labels       : list of row labels when select="label"
>     standardize  : "row" | "col" | "none"
>     cluster_rows : hierarchical clustering of rows (default True)
>     cluster_cols : hierarchical clustering of columns (default True)
>     filename     : output file name (required)
>     title        : optional plot title
>     cmap         : matplotlib colormap (default "RdBu_r")
>     nan_color    : color for missing cells (default "#DDDDDD")
>     figsize      : [width, height] in inches (default auto)
>     show_row_labels   : show row tick labels (default False)
>     show_col_labels   : show column tick labels (default True)
>
> Draw a heatmap of a 2D form.

## Inputs and outputs

Kind: `operator`. Operator ID: `heatmap`.
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

Implementation: `src/task/step/steps/heatmap.py` (`HeatmapStep`).
