<!-- operon:generated -->
# PDBML coordinate reader

## Purpose

> PDBML (PDB XML) coordinate reader.
>
> PDBML packs the same coordinate table as PDB into an XML document. This
> reader walks the ``atom_siteCategory`` entries with the standard library
> parser and mirrors :class:`PdbReader`: one row per atom and the field
> columns ``x``, ``y``, ``z``, ``occupancy``, ``bfactor``,
> ``residue_number``, ``chain``, ``resname`` and ``element``.
>
> Read the coordinate table of a PDBML document.

## Inputs and outputs

Kind: `reader`. Operator ID: `PdbmlReader`.
This Reader opens files with extensions: `.pdbml`.
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

Implementation: `src/reader/readers/pdbml_reader.py` (`PdbmlReader`).
