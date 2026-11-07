# Operator documentation and progressive discovery

Operon 1.0.0 / SDK 3.1 keeps operator protocol version 3. Documentation is
optional for compatibility with existing v3 installations and included for the
consolidated bundled library. New operators and Readers should ship it.

## Author once, install once

```text
pca.py                    # implementation and literal definition
pca.parameters.json       # parameter schema, defaults and UI hints
pca.md                    # scientific guidance
```

The scanner prefers `<module>.<Class>.md`, then `<module>.md`; for a package
`__init__.py`, the conventional document is `__init__.md`. An explicit literal
`documentation_file = "guide.md"` on the class overrides the convention. Relative
paths must remain inside the implementation directory; absolute paths, parent
traversal and non-Markdown files are rejected.

Use unique Markdown headings such as `Purpose`, `Inputs and outputs`, `Parameter
guidance`, `Interpretation`, `Limitations` and `Examples`. Explain units, assumptions,
normalization, missing-value handling, grouping and interpretation where relevant.
Link a real executable example or test. Do not call a parameter template a tested
scientific example. The scaffold includes a runnable test for its scaling operator.

The schema is the sole authority for names, defaults, bounds and choices. The
service generates the `parameters` and `contracts` sections on demand instead of
requiring authors to maintain duplicate tables. Saved workflow values stay in
their independent JSON and are not changed by documentation or default edits.

Include Markdown in setuptools package data, alongside parameter JSON and icons:

```toml
[tool.setuptools.package-data]
"lab_package" = ["*.json", "*.md", "*.svg", "*.png"]
```

`operon plugin check` reads AST, JSON and Markdown without importing calculation
code. `plugin build` verifies that the wheel contains the exact declared Markdown.
Installing a wheel or a whole library installs its documentation too. Reading it
does not install scientific dependencies or launch an analysis.

## Generated metadata and content identity

The optional descriptor `documentation` object carries:

- `path`: module-relative resource path;
- `sha256`: hash of the actual UTF-8 Markdown bytes;
- `summary`: a compact plain-text discovery hint;
- `sections`: unique heading slugs;
- `status`: `generated`, `authored`, or an explicit publisher claim of `reviewed`;
- `minimum_sdk`: `3.1.0`.

Full Markdown is not copied into every catalog response. Installation and refresh
retain immutable content-addressed copies under the profile's plugin directory.
New Markdown digests use UTF-8 with LF line endings, so Windows editors and clean
Git checkouts produce the same descriptor. Historical raw-byte digests remain
valid for their original cached or packaged resources.
An older registry generation or job can request its original documentation. A
missing historical resource produces an explicit error instead of silently
showing instructions for a different implementation. No Python import is needed.

Documentation-only changes do not affect numerical code identity. New wheel pins
use a separate `execution_sha` that excludes only validated declared Markdown
and parameter sidecars, their generated metadata and wheel RECORD checksums.
Frozen workflow values remain authoritative and are validated against the selected
schema before execution. Implementations must consume the provided execution
parameters, not reread defaults from their authoring JSON during a run. Markdown
and parameter sidecars are declarative resources, not runtime input files.
Code, resource declarations, binary dependencies and
other assets are still covered. The original archive SHA is
always retained and checked. Refresh can reuse existing code and dependency
targets without recompilation; old-style pins still require their exact archive.

## Efficient discovery for agents

All transports use `operon.operator_docs.OperatorDocs`:

```python
docs = OperatorDocs(plugin_manager)
docs.search("principal components", limit=10)
docs.describe(["pca"], sections=["purpose", "parameters", "contracts"])
docs.describe(["pca"], sections=["*"], generation=job_registry_generation)
```

Search reads the registry metadata once per generation and returns compact
summaries, never the full documentation library. `describe` accepts at most 20 IDs.
Omit `sections` to retrieve schemas, contracts and a section index without reading
Markdown. Ask for named sections, or `*` for the entire document. Search pagination
uses `offset` and `limit` (1–100); the response reports the total and generation.

Typical agent sequence: search candidates, request their contracts and relevant
guidance, inspect the data, validate a workflow, execute, inspect artifacts. UI
selection is optional; these queries work through the standalone service.

MCP/CLI now default to five relevance-ranked `brief` search summaries and the
`schema` describe view. Use `view=docs` / `--view docs` for selected Markdown without
repeating schemas; `full` retains the original complete descriptor. HTTP and the
Python service default to full for existing integrations. Search is lexical and
supports declared title aliases, not arbitrary translation. See the
[agent operating guide](agent_operations.md) for task-level retrieval and caching.

## Repository maintenance

```text
python scripts/build_operator_docs.py
python scripts/build_operator_docs.py --check
operon registry build --scope packages
```

The generator reads module/class docstrings using AST and preserves authored
pages. Generated companions are explicitly marked `<!-- operon:generated -->`;
they are never labelled scientifically reviewed. Replace that marker and refine
the page when providing authored guidance. A generated reference is a useful
starting point, not evidence that every algorithm has been scientifically
validated. Run the actual operator examples and domain tests separately.

Markdown changes become visible on explicit registry build/refresh or library
installation. Ordinary startup consumes the existing manifest; it does not scan
all implementation files or import them to regenerate documentation.
