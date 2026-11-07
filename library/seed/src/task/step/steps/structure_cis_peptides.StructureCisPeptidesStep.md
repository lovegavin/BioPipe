<!-- operon:generated -->
# Cis peptide bonds from omega dihedrals

## Purpose

> Cis peptide bonds from backbone omega dihedrals.
>
> Input: a PDB Form (``dims=[atom, field]``) as produced by ``PdbReader``.
> Output: 2D Form ``[bond, statistic]`` with ``omega``, ``abs_omega`` and an
> ``is_cis`` flag for every consecutive peptide bond of each chain.
>
> A bond is classified as cis when ``abs(omega) <= cis_threshold`` degrees
> (default 30).  Bonds that span a residue-numbering gap carry no peptide bond
> and are skipped.
>
> Measure omega dihedrals and flag cis peptide bonds.

## Inputs and outputs

Kind: `operator`. Operator ID: `structure_cis_peptides`.
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

Implementation: `src/task/step/steps/structure_cis_peptides.py` (`StructureCisPeptidesStep`).
