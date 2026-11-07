<!-- operon:generated -->
# gff_feature_stats

## Purpose

> Per-feature-type statistics for any GFF3/GTF Form.
>
> Input: Form from Gff3Reader or GtfReader.
>     data   2D float32, shape (n_records, n_fields)
>     dims   [record, field]
>     labels field = GFF3 column names (seqid, source, type, start,
>                    end, score, strand, phase, attributes)
>     info   missing_code=NaN, encoders={field: {label: encoder}}
>
> Output:
>     data   2D float32, shape (n_types, 6)
>     dims   [feature_type, statistic]
>     statistic = [count, total_length, mean_length, min_length,
>                  max_length, mean_exons_per_gene]
>
> mean_exons_per_gene is the ratio of "exon" records to "gene"
> records in the whole file; it is only meaningful for the "gene"
> row, and is 0 for every other feature type.
>
> Params:
>     record_dim : name of the record axis (default "record")
>     field_dim  : name of the field axis (default "field")
>     output     : context key for the result (default: step name)
>
> Per-feature-type length and count statistics for GFF3/GTF.

## Inputs and outputs

Kind: `operator`. Operator ID: `gff_feature_stats`.
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

Implementation: `src/task/step/steps/gff_feature_stats.py` (`GffFeatureStatsStep`).
