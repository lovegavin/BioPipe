<!-- operon:generated -->
# GafReader

## Purpose

> GO Annotation File (GAF) reader.
>
> Tab-separated, 17 fixed columns, comment lines start with ``!``.
>
>     db                    1  source database
>     db_object_id          2  database-specific identifier
>     db_object_symbol      3  gene symbol
>     qualifier             4  NOT / contributes_to / ...
>     go_id                 5  GO term identifier
>     db_reference          6  reference
>     evidence_code         7  EXP / IDA / ...
>     with_from             8  supporting identifiers
>     aspect                9  P / F / C
>     db_object_name       10  full name
>     db_object_synonym    11  pipe-separated synonyms
>     db_object_type       12  protein / gene / ...
>     taxon                13  NCBI taxonomy id
>     date                 14  annotation date
>     assigned_by          15  assigning group
>     annotation_extension 16  structured extension
>     gene_product_form_id 17  isoform identifier
>
> Reference:
>     https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/
>
> Layout
> ------
>     dims = [annotation, field]
>
>     ``annotation`` is one row per GAF annotation line.
>     ``field`` holds the 16 non-synonym column names above.
>
> ``db_object_synonym`` is a pipe-separated multi-valued column. It is
> read verbatim into ``info["db_object_synonym"]`` and declared parallel
> to the annotation axis. The column is removed from data so it can be
> exploded downstream.
>
> Label rules accepted:
>
>     builtin           the standard column names above
>     auto              position indices
>     {<field_dim>: <k>}  read column <k> as annotation labels
>     {name: pos, ...}  explicit mapping
>
> Info fields set:
>
>     missing_code         np.nan
>     db_object_synonym    list of strings
>     encoders             one encoder per non-numeric column
>
> Reader for GO Annotation Files (.gaf).

## Inputs and outputs

Kind: `reader`. Operator ID: `GafReader`.
This Reader opens files with extensions: `.gaf`.
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

Implementation: `src/reader/readers/gaf_reader.py` (`GafReader`).
