<!-- operon:generated -->
# interval_stats

## Purpose

> Per-chromosome interval statistics for any BED-like Form.
>
> Input: Form from BedReader (or any form with chrom/start/end columns).
>
> Output:
>     data   2D float32, shape (n_chroms, 7)
>     dims   [chrom, statistic]
>     statistic = [n_intervals, total_bp, mean_length, median_length,
>                  min_length, max_length, span_bp]
>     total_bp  = sum of (end - start) over all intervals
>     span_bp   = max(end) - min(start) on this chrom
>     median_length uses the middle value for odd counts, and the
>     arithmetic mean of the two central values for even counts.
>
> Params:
>     region_dim  : record axis name (default "region")
>     field_dim   : field axis name (default "field")
>     chrom_field : chrom column label (default "chrom")
>     start_field : start column label (default "chromStart")
>     end_field   : end column label   (default "chromEnd")
>     output      : context key for the result (default: step name)
>
> Per-chromosome interval count and length statistics.

## Inputs and outputs

Kind: `operator`. Operator ID: `interval_stats`.
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

Implementation: `src/task/step/steps/interval_stats.py` (`IntervalStatsStep`).
