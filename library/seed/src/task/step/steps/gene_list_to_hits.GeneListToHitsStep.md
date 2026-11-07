<!-- operon:generated -->
# gene_list_to_hits

## Purpose

> Build a hits matrix from a gene list and a universe matrix.
>
> Input:
>     universe : 2D Form [gene, term]. Only the labels on the gene
>                axis are used.
>     params   : ``genes`` = list of gene labels
>
> Output:
>     hits     : 2D Form [gene, term], containing only the rows of
>                the universe whose gene is in ``genes``. Values are
>                taken from ``universe > 0``.
>
> The output is a valid hits Form for ``enrich_go``: gene axis is a
> subset of the universe, term axis matches the universe. Sending the
> full universe with zeroed-out non-hit rows would make
> ``enrich_go`` count every universe gene as a hit gene (it uses the
> hits form's row count as ``n``), so the operator drops non-hit rows
> instead.
>
> Params:
>     genes    : list of gene labels (required)
>     gene_dim : gene axis (default "gene")
>     term_dim : term axis (default "go_term")
>     output   : context key (default: step name)

## Inputs and outputs

Kind: `operator`. Operator ID: `gene_list_to_hits`.
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

Implementation: `src/task/step/steps/gene_list_to_hits.py` (`GeneListToHitsStep`).
