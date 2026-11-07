<!-- operon:generated -->
# gene_structure

## Purpose

> Per-gene structure summary for any GFF3/GTF Form.
>
> Input: Form from Gff3Reader or GtfReader.
>     data   2D float32, shape (n_records, n_fields)
>     dims   [record, field]
>     labels field = GFF3 column names, including attributes
>     info   missing_code=NaN, encoders={field: {label: encoder}}
>
> Gene membership comes from the attributes column: exon and CDS
> records whose ``gene_id=`` (or ``Parent=``) matches a gene record
> belong to that gene. When no gene_id linkage is present at all,
> a positional fallback counts exon records contained in the gene
> span.
>
> Output:
>     data   2D float32, shape (n_genes, 5)
>     dims   [gene, statistic]
>     statistic = [n_exons, n_introns, gene_length, cds_total, strand]
>     strand = +1 or -1
>
> Params:
>     record_dim : name of the record axis (default "record")
>     field_dim  : name of the field axis (default "field")
>     output     : context key for the result (default: step name)
>
> Per-gene exon/intron/CDS summary for GFF3/GTF.

## Inputs and outputs

Kind: `operator`. Operator ID: `gene_structure`.
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

Implementation: `src/task/step/steps/gene_structure.py` (`GeneStructureStep`).
