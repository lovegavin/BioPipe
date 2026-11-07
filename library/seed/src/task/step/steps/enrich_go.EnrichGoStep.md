<!-- operon:generated -->
# enrich_go

## Purpose

> GO term enrichment by the hypergeometric test.
>
> Given a hit set and a background universe, both expressed as binary
> gene x term matrices, this step computes for every term:
>
>     N          total genes in the universe
>     n          total genes in the hit set
>     K          genes annotated to the term in the universe
>     k          genes annotated to the term in the hit set
>     expected   n * K / N
>     P          P(X >= k | hypergeometric(N, K, n))
>     Q          P adjusted by the requested multiple-testing method
>
> The output is a term x statistic matrix, one row per term retained.
>
> Layout
> ------
>     hits       dims: [gene_dim, term_dim]
>     universe   dims: [gene_dim, term_dim]
>     output     dims: [term_dim, "statistic"]
>
> Both inputs must share the same term labels. The hit set's genes
> must be a subset of the universe's genes; otherwise the caller must
> restrict the universe first.
>
> Params:
>     gene_dim       : name of the gene dimension (default "gene")
>     term_dim       : name of the term dimension (default "go_term")
>     correction     : fdr | bonferroni | holm | hommel | fdr_by
>                      (default "fdr")
>     min_term_size  : drop terms with fewer than this many genes in
>                      the universe (default 1)
>     output         : context key for the result (default: step name)
>
> Hypergeometric enrichment of one term axis over two inputs.

## Inputs and outputs

Kind: `operator`. Operator ID: `enrich_go`.
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

Implementation: `src/task/step/steps/enrich_go.py` (`EnrichGoStep`).
