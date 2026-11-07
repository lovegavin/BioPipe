# Reference operator library

This directory is independently owned and versioned from the Operon application.

**Operon Operator Library v5.0.0** keeps `export_results` as the single
parameterized output operator for intermediate branches, native-file reuse and
CSV/TSV/NPY/FASTA/PDB/mmCIF exports. Structure predictors, Flye assembly, Vina
poses, LigandMPNN packing and PDBQT preparation now register their original files;
FASTA forms and the FASTA Reader carry `info.sequences`. See the
[operator guide](seed/src/task/step/steps/export_results.ExportResultsStep.md).

- `seed/src/task/step/steps/`: operator Python, parameter JSON, Markdown and assets.
- `seed/src/reader/readers/`: Reader implementations and their sidecars.
- `seed/operon/builtin_packages.json`: statically compiled v3 provider manifest.
- `seed/operon/environments.json`: optional named-environment recipes.
- `seed/routes/` and `seed/src/web/builtin_routes.json`: source and compiled routes.
- `seed/operator_index.json`, `seed/reader_index.json`: documentation indexes.
- `release.json`: library version and compatible released build application.
- `pyproject.toml`: separately installable factory seed distribution.

From the repository root, run `python -m operon registry build` after editing
declarations. Run `python scripts/build_operator_docs.py` to maintain generated
documentation; authored pages are preserved. No operator module is imported by
these maintenance commands.

Application code must depend on the SDK contract, not import a particular
analysis implementation. Keep authoring paths inside the seed stable: legacy
Python entry-point names are deliberate compatibility identifiers.

See [ownership and packaging](../docs/application_library_boundary.md) and
[independent release instructions](../docs/library_releases.md).
