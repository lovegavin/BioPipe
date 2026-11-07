# Find and understand an operator

1. Search with `operon_operator_search(query="principal components", limit=5)`
   or `operon operators search --query "principal components" --limit 5`.
   Search uses IDs, titles, declared aliases and descriptions, not an LLM.
   Prefer an exact ID or a short domain term. If a translated query has no hits,
   try the domain's English name or declared alias. Page only when necessary.
2. Request `operon_operator_describe(ids=["pca"], view="schema")` or
   `operon operators describe pca --view schema`. This returns parameter schema,
   contracts and a documentation section index without reading Markdown.
3. For interpretation or examples use `view="docs", sections=["purpose","examples"]`
   (CLI: `--view docs --section purpose --section examples`). Choose section names
   from the returned index. Generated pages are reference material, not evidence
   that a scientific method/example has been validated.
4. Request `view="full"` only when implementation/dependency details are needed.
   For a historical job use `generation` from its artifact provenance or full job.

Search defaults to `view="brief"`; `view="full"` retains the original metadata
response. Describe defaults to `schema`. The HTTP API keeps its full defaults for
existing integrations. Cache per registry generation, and refresh after a library
change; do not reuse an old schema silently with a new implementation.

Respect required fields, enum choices, dimensions and named input ports. Frozen
workflow values take precedence over current defaults. Omit engine-owned
`_input_names`. Use `operon schema graph` for the actual graph JSON schema.
