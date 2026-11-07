<!-- operon:generated -->
# Windowed gene density

## Purpose

> Windowed gene density across every sequence of a GFF3/GTF annotation.
>
> Input: Form from GffReader or GtfReader.
> Output: 2D [window, statistic]
>
>     window_start, window_end, n_features, features_per_kb,
>     aligned_bp, aligned_fraction
>
> ``aligned_bp`` is the union of the selected feature intervals clipped to
> the window, so overlapping genes are counted once.  ``genome_size`` per
> sequence is the largest feature end (GFF files do not declare chromosome
> length); the trailing partial window is therefore bounded by the last
> annotated base, not by the true replicon end.
>
> Gene (or CDS) density in fixed windows along each sequence.

## Inputs and outputs

Kind: `operator`. Operator ID: `genome_gene_density`.
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

Implementation: `src/task/step/steps/genome_gene_density.py` (`GenomeGeneDensityStep`).
