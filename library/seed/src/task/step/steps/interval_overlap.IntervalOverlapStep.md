<!-- operon:generated -->
# interval_overlap

## Purpose

> Pairwise interval overlap between two BED forms (bedtools intersect style).
>
> Inputs: two Forms from BedReader (or any form with chrom/start/end
> columns). Each record is a half-open interval [start, end) on a chrom.
>
> Output: every (A, B) pair whose intervals overlap by at least
> ``min_overlap`` bases.
>     data   2D float32, shape (n_pairs, 7)
>     dims   [pair, statistic]
>     statistic = [overlap_start, overlap_end, overlap_length,
>                  a_length, b_length,
>                  overlap_fraction_a, overlap_fraction_b]
>     info["chrom"]  axis-parallel, chromosome of each pair
>     info["a_id"]   axis-parallel, index of the A interval
>     info["b_id"]   axis-parallel, index of the B interval
>
> Both inputs are grouped by chromosome and scanned with a sweep-line:
> each A-start is matched against every currently open B interval, and
> vice versa. Each pair is recorded exactly once.
>
> Params:
>     a_region_dim  : A record axis (default "region")
>     a_field_dim   : A field axis (default "field")
>     a_chrom_field : A chrom column (default "chrom")
>     a_start_field : A start column (default "chromStart")
>     a_end_field   : A end column (default "chromEnd")
>     b_region_dim  : B record axis (default "region")
>     b_field_dim   : B field axis (default "field")
>     b_chrom_field : B chrom column (default "chrom")
>     b_start_field : B start column (default "chromStart")
>     b_end_field   : B end column (default "chromEnd")
>     min_overlap   : minimum overlap in bp (default 1)
>     max_output    : abort with an error above this many pairs (default 1000000)
>     output        : context key for the result (default: step name)
>
> Pairwise overlap of intervals between two BED forms.

## Inputs and outputs

Kind: `operator`. Operator ID: `interval_overlap`.
Input count: `2`.
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

Implementation: `src/task/step/steps/interval_overlap.py` (`IntervalOverlapStep`).
