<!-- operon:generated -->
# PLINK .tped genotype reader

## Purpose

> PLINK 1.9 transposed pedigree (.tped / .tfam) reader.
>
> Reader for PLINK 1.9 transposed genotype files.
>
> Each ``.tped`` row is ``chrom id cm pos`` followed by two allele codes
> per sample; ``.tfam`` lists the samples. Codes are ``0`` (missing),
> ``1`` (first allele) and ``2`` (second allele); the value stored for a
> call is the count of the first allele, so heterozygous calls are ``1``.

## Inputs and outputs

Kind: `reader`. Operator ID: `TpedReader`.
This Reader opens files with extensions: `.tped`.
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

Implementation: `src/reader/readers/tped_reader.py` (`TpedReader`).
