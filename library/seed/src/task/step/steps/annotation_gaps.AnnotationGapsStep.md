<!-- operon:generated -->
# annotation_gaps

## Purpose

> Inter-gene gap statistics for any GFF3/GTF Form.
>
> Groups gene records by seqid, sorts them by start position, and
> reports the gap between every pair of consecutive genes.
>
> gap_length = next.start - current.end - 1
>
> Genes overlapping or touching each other (gap_length < 0 or 0)
> are skipped. Gaps are reported per chromosome in start order.
>
> Output:
>     data   2D float32, shape (n_gaps, 5)
>     dims   [gap, statistic]
>     statistic = [gap_length, left_start, left_end, right_start, right_end]
>     info["seqid"]      axis-parallel, name of the source chromosome
>     info["left_gene"]  axis-parallel, "seqid:start-end" of the left gene
>     info["right_gene"] axis-parallel, "seqid:start-end" of the right gene
>
> Params:
>     record_dim : name of the record axis (default "record")
>     field_dim  : name of the field axis (default "field")
>     min_gap    : report only gaps >= this many bp (default 0)
>     output     : context key for the result (default: step name)
>
> Inter-gene gap lengths for GFF3/GTF annotation QC.

## Inputs and outputs

Kind: `operator`. Operator ID: `annotation_gaps`.
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

Implementation: `src/task/step/steps/annotation_gaps.py` (`AnnotationGapsStep`).
