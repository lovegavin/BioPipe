<!-- operon:generated -->
# annotate

## Purpose

> Attach reference fields onto a target by key label.
>
> Aligns two forms on a shared key dimension by label, then copies the
> requested reference fields into the target's ``info``, declaring them
> parallel to the target key axis.
>
> A reference field may come from either:
>
> * a data column: its label on ``field_dim``; encoded columns carry
>   their encoder across so codes stay comparable.
> * an info field: declared parallel to ``source_dim`` in
>   ``axis_info``; typically read verbatim by ``info_columns``.
>
> This is the standard way to enrich a table with an external lookup
> table (variant annotations, gene descriptions, taxon metadata,
> sample covariates) without merging data dimensions.
>
> Layout
> ------
>     target     dims: [key_dim, ...]
>     reference  dims: [key_dim_ref, field_dim]
>     output     dims: same as target
>
> Alignment
> ---------
> Matching is by label, not by position. For every target label on
> ``target_dim``, the reference row whose ``source_dim`` label equals
> it supplies the values. Target labels without a reference match get
> NaN.
>
> The alignment is computed once as a position lookup array and applied
> with numpy fancy indexing, so the cost is O(n) in C, not in Python.
>
> Params:
>     target_dim : key dimension on the target (required)
>     source_dim : key dimension on the reference (required)
>     fields     : reference field names to attach (required)
>     field_dim  : reference data dimension (default: the other 2D dim)
>     output     : context key for the result (default: step name)
>
> Attach reference fields onto a target by key label.

## Inputs and outputs

Kind: `operator`. Operator ID: `annotate`.
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

Implementation: `src/task/step/steps/annotate.py` (`AnnotateStep`).
