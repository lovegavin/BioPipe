<!-- operon:generated -->
# peak_nearest_gene

## Purpose

> Associate every BED interval with its nearest annotated gene.
>
> Inputs:
>     A  BED   [region, field]  with chrom / chromStart / chromEnd
>     B  GFF3  [record, field]  with seqid / type / start / end / strand
>
> For every A interval, find the gene record on the same chromosome
> whose span is closest. Overlapping intervals get distance 0.
>
> Distance:
>     overlap          -> 0
>     A ends before B  -> B.start - A.end
>     A starts after B -> A.start - B.end
>
> Chromosome names are normalised before matching: if one side uses
> "chr1" and the other "1", the "chr" prefix is added to the shorter
> form. A column may or may not be encoded: if the reader encoded it,
> the encoder's inverse is used; otherwise the numeric value is
> stringified without a trailing ".0".
>
> Output:
>     data   2D float32, shape (n_peaks, 5)
>     dims   [peak, statistic]
>     statistic = [distance, gene_start, gene_end, gene_length, strand]
>     info["peak_id"]  axis-parallel, index of the A interval
>     info["gene_id"]  axis-parallel, gene id from attributes or "g<i>"
>     info["chrom"]    axis-parallel, normalised chromosome name
>
> Params:
>     a_region_dim   : A record axis  (default "region")
>     a_field_dim    : A field axis   (default "field")
>     a_chrom_field  : A chrom column (default "chrom")
>     a_start_field  : A start column (default "chromStart")
>     a_end_field    : A end column   (default "chromEnd")
>     b_record_dim   : B record axis  (default "record")
>     b_field_dim    : B field axis   (default "field")
>     b_chrom_field  : B seqid column (default "seqid")
>     b_start_field  : B start column (default "start")
>     b_end_field    : B end column   (default "end")
>     b_strand_field : B strand column (default "strand")
>     feature_type   : only use B records whose type equals this
>                      (default "gene"; set to "" to disable)
>     max_distance   : report only peaks with distance <= this many bp
>                      (default null = no limit)
>     output         : context key for the result (default: step name)
>
> Assign every BED interval to its nearest annotated gene.

## Inputs and outputs

Kind: `operator`. Operator ID: `peak_nearest_gene`.
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

Implementation: `src/task/step/steps/peak_nearest_gene.py` (`PeakNearestGeneStep`).
