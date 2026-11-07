<!-- operon:generated -->
# Gff3Reader

## Purpose

> GFF3 (Generic Feature Format version 3) reader.
>
> A 9-column tab-delimited text file. No header. Lines starting with
> ``#`` are skipped (both ``##`` directives and ``#`` comments).
> Column names follow the GFF3 specification:
>
>     0  seqid       chromosome or scaffold name
>     1  source      program or database
>     2  type        feature type (gene, mRNA, exon, CDS, ...)
>     3  start       1-based inclusive start
>     4  end         1-based inclusive end
>     5  score       floating point or '.'
>     6  strand      '+', '-', or '.'
>     7  phase       '0', '1', '2', or '.'
>     8  attributes  semicolon-separated key=value pairs:
>                    ``ID=gene1;Name=DDX11;biotype=protein_coding``
>
> Compression is handled by the framework; this reader sees plain
> files only.
>
> Label rules accepted:
>
>     builtin           the standard GFF3 column names above
>     auto              position indices "0", "1", ...
>     {<other_dim>: <k>}  read column <k> as the other dim's labels
>                         (removed from data)
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``auto``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Non-numeric columns are encoded. The encoder instance used for each
> column is recorded in ``info["encoders"]``.
>
> Reference
> ---------
> GFF3 specification:
> https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
>
> Info fields set:
>
>     missing_code      np.nan
>     encoders          present only when a column was encoded
>
> Reader for .gff / .gff3 files.

## Inputs and outputs

Kind: `reader`. Operator ID: `Gff3Reader`.
This Reader opens files with extensions: `.gff`, `.gff3`.
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

Implementation: `src/reader/readers/gff3_reader.py` (`Gff3Reader`).
