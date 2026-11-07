<!-- operon:generated -->
# Reader for .gmt gene-set files

## Purpose

> GMT gene-set reader.
>
> A GMT file has one gene set per line::
>
>     set_name<TAB>description<TAB>gene1<TAB>gene2 ...
>
> The result is a binary gene x set matrix. Genes are ordered by first
> appearance in the file; duplicate set names are rejected, while duplicate
> genes inside one set are collapsed.
>
> The reader deliberately does **not** perform enrichment. It only
> preserves set membership so `ora` / `gsea` can apply their own
> statistics and multiple-testing policy.

## Inputs and outputs

Kind: `reader`. Operator ID: `GmtReader`.
This Reader opens files with extensions: `.gmt`.
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

Implementation: `src/reader/readers/gmt_reader.py` (`GmtReader`).
