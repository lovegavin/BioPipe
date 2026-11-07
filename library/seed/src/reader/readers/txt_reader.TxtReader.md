<!-- operon:generated -->
# TxtReader

## Purpose

> Generic text reader that delegates to another reader.
>
> Handles .txt and .tab extensions that have no dedicated reader.
> Parsing is delegated to another registered reader, selected by name.
>
> Params:
>     reader : name of the reader to delegate to, matched against the
>              class name with "Reader" stripped and lowercased.
>              Examples: "csv" -> CsvReader, "bed" -> BedReader,
>              "gtf" -> GtfReader. Default "csv".
>     All other args are forwarded to the delegated reader.
>
> When the delegate is CsvReader and ``sep`` is not given, a tab
> separator is assumed for .txt and .tab files.
>
> Read generic text files by delegating to another reader.

## Inputs and outputs

Kind: `reader`. Operator ID: `TxtReader`.
This Reader opens files with extensions: `.txt`, `.tab`.
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

Implementation: `src/reader/readers/txt_reader.py` (`TxtReader`).
