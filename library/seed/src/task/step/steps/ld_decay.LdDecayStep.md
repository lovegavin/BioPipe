<!-- operon:generated -->
# LD decay

## Purpose

> Linkage disequilibrium decay over genomic distance.
>
> For every pair of variants on one chromosome the squared Pearson
> correlation of the alt allele dosage (0 .. ploidy) is computed, which equals
> ``allel.rogers_huff_r`` squared for complete hard calls. Pairs are binned by
> physical distance in ``n_bins`` equal-width bins between 0 and
> ``max_distance`` base pairs; zero-distance pairs (duplicate positions) are
> excluded because they are not independent loci.
>
> Input: hard-call genotypes, [variant, sample], with ``pos`` and ``chrom``
> read from the variant axis labels or from ``axis_info``. Only complete
> variants (no missing call) and polymorphic variants (non-zero variance)
> enter the correlation. The input must span a single chromosome; subset a
> chromosome first when a VCF covers more.
>
> Output: dims [distance_bin, statistic] with columns
> (bin_start, bin_end, n_pairs, mean_r2, median_r2). Empty bins keep NaN
> values and ``n_pairs`` 0.
>
> ``max_pairs`` is a guard against quadratic blow-up: the run fails with the
> number of candidate pairs instead of materialising an unbounded matrix.

## Inputs and outputs

Kind: `operator`. Operator ID: `ld_decay`.
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

Implementation: `src/task/step/steps/ld_decay.py` (`LdDecayStep`).
