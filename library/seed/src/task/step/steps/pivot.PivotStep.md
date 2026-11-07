<!-- operon:generated -->
# pivot

## Purpose

> Turn a long table into a wide matrix by two categorical columns.
>
> The input is a 2D form whose ``field_dim`` holds a set of named
> columns. Two of those columns are chosen: one becomes the row axis
> of the output, the other becomes the column axis. A third column may
> supply the cell value; without it, every observed pair contributes 1.
>
> This is the standard way to build a gene x GO-term membership matrix
> from a GAF file, a sample x feature matrix from a long CSV, or any
> pair-count table that downstream matrix operators can consume.
>
> Layout
> ------
>     input   dims: [pair, field]
>     output  dims: [<index_name>, <columns_name>]
>
> Duplicate (index, column) pairs are combined by ``agg``.
>
> A hard cell-count cap protects the runtime from accidentally
> materialising a huge dense matrix. When the cap is exceeded, filter
> the input to a smaller subset before pivoting.
>
> Params:
>     index_label   : column label on the input field dim, becomes the
>                     row axis (required)
>     columns_label : column label on the input field dim, becomes the
>                     column axis (required)
>     values_label  : column label supplying cell values; without it
>                     every observed pair contributes 1
>     index_name    : name of the output row dim (default: index_label)
>     columns_name  : name of the output column dim (default: columns_label)
>     agg           : sum | first | max | min | count (default sum)
>     output        : context key for the result (default: step name)
>
> Pivot a long 2D table into a wide matrix by two categorical columns.

## Inputs and outputs

Kind: `operator`. Operator ID: `pivot`.
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

Implementation: `src/task/step/steps/pivot.py` (`PivotStep`).
