<!-- operon:generated -->
# BLAST outfmt 6 reader

## Purpose

> BLAST tabular (outfmt 6) reader.
>
> Reads the 12 standard BLAST columns. Additional outfmt 6 columns are
> ignored; use a dedicated reader for custom column sets.

## Inputs and outputs

Kind: `reader`. Operator ID: `BlastTabularReader`.
This Reader opens files with extensions: `.blast6`, `.b6`, `.blasttab`.
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

Implementation: `src/reader/readers/blast_tabular_reader.py` (`BlastTabularReader`).
