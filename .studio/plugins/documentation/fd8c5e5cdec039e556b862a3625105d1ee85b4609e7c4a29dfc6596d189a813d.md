<!-- biopipe:generated -->
# Summary reader for GenBank (.gb/.gbk/.gbff) flat files

## Purpose

> GenBank flat-file summary reader.
>
> One output row per LOCUS record.  The sequence itself is not returned;
> ``length``, GC fraction and the number of top-level feature keys are.
> This is a dependency-free parser for the common GenBank flat-file layout.

## Inputs and outputs

Kind: `reader`. Operator ID: `GenBankReader`.
This Reader opens files with extensions: `.gb`, `.gbk`, `.gbff`.
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

## Limitations

Declared memory modes: full. BioPipe retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/reader/readers/genbank_reader.py` (`GenBankReader`).
