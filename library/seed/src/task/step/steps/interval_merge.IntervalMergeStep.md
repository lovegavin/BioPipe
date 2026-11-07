<!-- operon:generated -->
# interval_merge

## Purpose

> Merge overlapping BED intervals per chromosome (bedtools merge style).
>
> Input: Form from BedReader.
>     data   2D float32, shape (n_records, n_fields)
>     dims   [region, field]
>     labels field = BED column names (chrom, chromStart, chromEnd, ...)
>     info   missing_code=NaN, encoders={field: {label: encoder}}
>
> Only chrom, chromStart and chromEnd are read. Records are grouped
> by chromosome, sorted by start, and consecutive intervals are merged
> when the gap between them is at most ``min_overlap`` bases:
>
>     gap = next.start - current.end
>     merge when gap <= min_overlap
>
> With min_overlap=0, overlapping and book-ended intervals (gap == 0)
> are merged. Negative gaps (real overlap) are always merged.
>
> Output:
>     data   2D float32, shape (n_merged, 4)
>     dims   [merged_region, statistic]
>     statistic = [start, end, length, n_intervals]
>     length = end - start (0-based half-open)
>     info["chrom"]  axis-parallel, chromosome of each merged region
>
> Params:
>     region_dim  : name of the record axis (default "region")
>     field_dim   : name of the field axis (default "field")
>     chrom_field : name of the chrom column (default "chrom")
>     start_field : name of the start column (default "chromStart")
>     end_field   : name of the end column   (default "chromEnd")
>     min_overlap : merge intervals whose gap is <= this value (default 0)
>     output      : context key for the result (default: step name)
>
> Merge overlapping BED intervals per chromosome.

## Inputs and outputs

Kind: `operator`. Operator ID: `interval_merge`.
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

Implementation: `src/task/step/steps/interval_merge.py` (`IntervalMergeStep`).
