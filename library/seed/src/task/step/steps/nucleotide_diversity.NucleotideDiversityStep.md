<!-- operon:generated -->
# Nucleotide diversity

## Purpose

> Nucleotide diversity (pi) over the whole input or fixed genomic windows.
>
> Nucleotide diversity is the average number of differences between two
> chromosomes sampled from the input:
>
>     pi            sum over variants of the mean pairwise difference
>     pi_per_site   pi / n_bases
>
> Input: hard-call genotypes, [variant, sample], alt allele counts in
> [0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the
> variant axis labels or from ``axis_info``. Windows follow scikit-allel:
> they start at the first annotated position, advance by ``step_size``
> (default ``window_size``), are ``window_size`` long, and the last window
> ends at the last position.
>
> Output: dims [window, statistic] with columns
> (start, end, n_variants, n_bases, pi, pi_per_site, mean_pairwise_difference).
> Without ``pos`` there is one row per chromosome, start/end and n_bases are
> NaN, and only the absolute ``pi`` is meaningful.

## Inputs and outputs

Kind: `operator`. Operator ID: `nucleotide_diversity`.
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

Implementation: `src/task/step/steps/nucleotide_diversity.py` (`NucleotideDiversityStep`).
