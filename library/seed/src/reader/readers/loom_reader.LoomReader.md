<!-- operon:generated -->
# Reader for .loom files

## Purpose

> Loom reader for single-cell matrices.
>
> A Loom file is HDF5. The default matrix is ``/matrix`` with shape
> (genes, cells); row identifiers live in ``/row_attrs/GeneIDs`` and
> column identifiers in ``/col_attrs/CellID``. Common alternatives
> (``Gene``/``GeneIDs`` and ``CellID``/``CellIDs``) are accepted.
>
> The reader keeps the matrix dense (Loom matrices are normally dense)
> and preserves the first-axis/second-axis order from the manifest.

## Inputs and outputs

Kind: `reader`. Operator ID: `LoomReader`.
This Reader opens files with extensions: `.loom`.
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

Implementation: `src/reader/readers/loom_reader.py` (`LoomReader`).
