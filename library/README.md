# Reference operator library

This directory is independently owned and versioned from the BioPipe application.

- `seed/src/task/step/steps/`: operator Python, parameter JSON, Markdown and assets.
- `seed/src/reader/readers/`: Reader implementations and their sidecars.
- `seed/biopipe/builtin_packages.json`: statically compiled v3 provider manifest.
- `seed/biopipe/environments.json`: optional named-environment recipes.
- `seed/routes/` and `seed/src/web/builtin_routes.json`: source and compiled routes.
- `seed/operator_index.json`, `seed/reader_index.json`: documentation indexes.
- `release.json`: library version and compatible released build application.
- `pyproject.toml`: separately installable factory seed distribution.

From the repository root, run `python -m biopipe registry build` after editing
declarations. Run `python scripts/build_operator_docs.py` to maintain generated
documentation; authored pages are preserved. No operator module is imported by
these maintenance commands.

Application code must depend on the SDK contract, not import a particular
analysis implementation. Keep authoring paths inside the seed stable: legacy
Python entry-point names are deliberate compatibility identifiers.

See [ownership and packaging](../docs/application_library_boundary.md) and
[independent release instructions](../docs/library_releases.md).
