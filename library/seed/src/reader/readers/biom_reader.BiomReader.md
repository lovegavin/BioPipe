<!-- operon:generated -->
# Reader for .biom tables (JSON or HDF5)

## Purpose

> BIOM reader for microbiome tables.
>
> Supports BIOM 2.x JSON and HDF5 files. BIOM stores observations
> (taxa) as rows and samples as columns; the matrix is returned as
> (sample, taxon) so it composes naturally with metadata tables. The
> ``taxon`` axis keeps observation IDs (and optionally taxonomy strings).
>
> BIOM's biological table is sparse. It is densified here because Loom-
> like sparse disk preparation is not yet advertised by this Reader.
> For very large tables a future disk protocol should be added rather
> than silently raising memory pressure.

## Inputs and outputs

Kind: `reader`. Operator ID: `BiomReader`.
This Reader opens files with extensions: `.biom`.
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

Implementation: `src/reader/readers/biom_reader.py` (`BiomReader`).
