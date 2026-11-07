<!-- operon:generated -->
# Site frequency spectrum

## Purpose

> Site frequency spectrum for biallelic hard-call genotypes.
>
> For every variant the derived (alt) allele count is the number of alt
> alleles among the called chromosomes. The spectrum counts how many
> variants carry each count.
>
> Input: hard-call genotypes, [variant, sample], with the same number of
> called chromosomes on every variant (for example a complete genotype
> matrix, or a matrix subset that keeps only complete variants). Missing
> calls make the number of chromosomes vary between variants, which makes
> the folded spectrum ambiguous, so they are rejected instead of silently
> masked.
>
> Output: dims [frequency, statistic] with columns (sites, proportion).
> Unfolded bins are 1 .. n-1, folded bins are 1 .. n//2 with minor allele
> counts (as in ``allel.sfs`` and ``allel.sfs_folded``). Monomorphic sites
> (frequency 0 and n) are not part of the spectrum; ``proportion`` divides
> the bin count by the total number of input variants.

## Inputs and outputs

Kind: `operator`. Operator ID: `site_frequency_spectrum`.
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

Implementation: `src/task/step/steps/site_frequency_spectrum.py` (`SiteFrequencySpectrumStep`).
