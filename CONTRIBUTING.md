# Contributing to Operon

Operator/Reader-only updates follow [independent library releases](docs/library_releases.md).
Use a `library-v…` tag and update `library/release.json`; do not bump the Studio
application or rebuild an EXE unless new engine/SDK behavior is required.

Read [the documentation index](docs/README.md), then search the existing catalog
before adding another operator. The current source lives on `main`; historical
release branches and the legacy archive are not alternative authoring protocols.

## Add an operator or Reader

1. Start with `operon plugin init <directory>`; use `--template reader` for a
   Reader. Follow the generated code, parameter JSON, Markdown and package files.
2. Declare protocol v3 input/output contracts, dependencies and supported memory
   modes accurately. Keep defaults/schema in the adjacent parameter JSON.
3. Explain purpose, input meaning, outputs, parameters, dependencies and limits
   in the Markdown guide. Include a small executable example. Never present an
   automatically generated description as scientific validation.
4. Test numerical results and metadata using the SDK harness. For large inputs,
   test the promised stream/disk behavior and cancellation paths as applicable.
5. Run `operon plugin check <directory>`, `operon plugin test <directory>` and
   `operon plugin build <directory>`. Install the resulting package with
   `operon plugin install <package>`; Studio and headless services share it.

For bundled extensions, use the existing provider and add code, parameter JSON
and Markdown under `library/seed/src/task/step/steps/` or `library/seed/src/reader/readers/`. Private helper
files start with `_`. Run `python scripts/build_operator_docs.py` and
`python -m operon registry build`, then `python -m operon registry check`.
Maintenance reads static declarations; startup does not execute every module.

See the [SDK guide](docs/sdk_quickstart.md), [Reader guide](docs/reader_extensions.md),
[Step guide](docs/step_extensions.md) and [protocol](docs/operator_protocol.md).
The parameter schema is the machine-readable authority; Markdown explains its
scientific meaning. Do not maintain a second handwritten schema in the guide.

## Extend the application

Put workflow, task and artifact behavior in the shared application services.
Expose it through adapters rather than implementing separate CLI, MCP and GUI
engines. Preserve revision checks, explicit execution permission, frozen route
values, memory admission and SSH file ownership. Prefer bounded metadata queries
over reading whole matrices or copying result datasets.

Run focused regression tests and relevant integration tests. Use synthetic or
properly attributed public fixtures; never commit private inputs, credentials,
local profiles, generated job directories or machine-specific paths. Keep
technical documentation in English and record material validation limits.
