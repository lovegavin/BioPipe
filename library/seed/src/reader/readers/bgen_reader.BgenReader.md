<!-- operon:generated -->
# BgenReader

## Purpose

> BGEN reader.
>
> BGEN stores genotype probabilities (P(AA), P(AB), P(BB)) per variant
> per sample. This reader computes the expected ALT allele dosage:
>
>     dosage = P(AB) + 2 * P(BB)
>
> Layout:
>     axis 0 = variant, axis 1 = sample.
>
> Backed by bgen-reader, which supports BGEN 1.2 and 1.3 and handles
> compression internally. External wrappers are handled by the framework.
>
> Label rules accepted:
>
>     builtin           variant: ids from the BGEN
>                       sample:  samples from the BGEN
>     auto              position indices "0", "1", ...
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``builtin``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Reference
> ---------
> BGEN specification:
> https://www.well.ox.ac.uk/~gav/bgen_format/
>
> Info fields set:
>
>     missing_code      np.nan
>     ploidy            2
>
> Reader for .bgen files.

## Inputs and outputs

Kind: `reader`. Operator ID: `BgenReader`.
This Reader opens files with extensions: `.bgen`.
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

Implementation: `src/reader/readers/bgen_reader.py` (`BgenReader`).
