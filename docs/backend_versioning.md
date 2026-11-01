# Backend versioning

This page defines how the **backend/application version** of BioPipe is managed.
It is the version in `pyproject.toml` and `biopipe/__init__.py`, reported by
`biopipe --version` and used by the generated plugin dependency bound.

## Independent version axes

| Axis | Owner | Declared in | Current |
| --- | --- | --- | --- |
| Backend application | backend maintainer | `pyproject.toml`, `biopipe/__init__.py` | **1.14.0** |
| Frontend / desktop package | frontend maintainer | `frontend/package.json` | 0.116.2 (independent) |
| Authoring protocol and SDK | protocol maintainer | `protocol_version` 3, `biopipe_sdk` 3.1.0 | v3 / 3.1.0 |
| Operator library bundle | release tooling | `.biopipe-library.zip` build | tracks a build, not this version |

A backend increment never silently changes the protocol version, the SDK version
or the frontend package version. A frontend release does not require a backend
increment unless it depends on new backend behavior, and a backend release does
not renumber the frontend.

## Rules

**MAJOR (X).** Milestone or architectural change, kept for long intervals. A
breaking change to backend behavior, plugin compatibility, or a removed/renamed
operator or Reader ID requires a MAJOR increment.

**MINOR (Y).** One increment per **expansion batch** that adds or removes
operators, Readers, providers or route templates. A batch gets exactly one MINOR
increment, even when it is delivered in several commits or contains several
capability families. Numbers are not skipped.

**PATCH (Z).** One increment per user-visible change set that does **not** expand
the library: bug fixes, refactors, documentation, tests, dependency or build
changes. PATCH is not used to publish new capabilities.

Examples:

```text
1.0.0  first backend release (protocol v3 integration)
1.1.0  expansion batch: five population-genetics operators
1.1.1  fix: a window edge case in an existing statistic
1.2.0  expansion batch: Arrow reader, seasonal decomposition and Fst-family statistics
1.3.0  expansion batch: Faith PD, UniFrac distances, patristic distance and PhyloXML
1.4.0  expansion batch: causal-inference operators and a MuData reader
1.6.0  expansion batch: SIMPER, MRPP, species accumulation and cophenetic correlation
1.7.0  expansion batch: Moran's I, indicator species, pairwise alignment and PDBML
1.8.0  expansion batch: PCoN-M, Cuzick trend test, Fisher's alpha and a TPED reader
1.9.0  expansion batch: MANOVA, quadratic discriminant analysis, k nearest neighbours and a logistic mixed model
1.10.0  expansion batch: exact Poisson tests, binomial confidence intervals, chi-square goodness of fit and redundancy analysis
1.12.0  expansion batch: Lilliefors, Cox-Stuart, Mann-Kendall rank and Pearson normality tests
1.13.0  expansion batch: Mood scale test, two-sample F test, D'Agostino skewness and Anscombe-Glynn kurtosis tests
1.14.0  expansion batch: linear discriminant analysis, simple correspondence analysis, nestedness and Rényi diversity
1.15.0  next expansion batch
2.0.0  breaking change to plugin compatibility or operator IDs
```

## Version touch points

1. `pyproject.toml` — `[project] version`.
2. `biopipe/__init__.py` — `__version__`.
3. `docs/releases/vX.Y.Z.md` — release notes for the version.
4. Current counts and version text: `README.md`, `docs/UNIFIED_MAIN.md`,
   `docs/package_protocol.md`.
5. Reinstall the editable package after the bump so
   `importlib.metadata.version("biopipe-studio")` matches
   `biopipe.__version__`; a stale `*.egg-info` otherwise shadows the new value.

Generated indexes (`biopipe/builtin_packages.json`,
`docs/reference/operator_index.json`, `docs/reference/reader_index.json`,
`src/web/builtin_routes.json`) are outputs of `biopipe registry build` and
`scripts/build_operator_docs.py`. Never hand-edit them.

## Release procedure: expansion batch

1. Implement the new operators/Readers in the protocol v3 three-file form
   (`<module>.py`, `<module>.<Class>.parameters.json`,
   `<module>.<Class>.md`) and declare `provider` plus a literal `definition`.
2. Add focused tests: a hand-computable case and, where a trusted implementation
   exists (R, scikit-allel, scikit-learn, statsmodels, PLINK, …), a value-by-value
   comparison. Failure paths are part of the test set.
3. `python -m biopipe registry check` must report no errors, then
   `python -m biopipe registry build` regenerates the package and route indexes.
4. `python scripts/build_operator_docs.py` regenerates the adjacent Markdown and
   the documentation indexes; `--check` must be clean afterwards.
5. Increment MINOR, write `docs/releases/vX.Y.Z.md`, update the counts above.
6. Run the focused tests. Run the full suite only when the change touches shared
   core behavior, the registry discovery layer, or a release candidate is being
   prepared.
7. Commit, create the annotated tag `vX.Y.Z`, and push `main` and the tag. Never
   move or reuse a published tag.
8. Sync the Windows test copy and verify registry counts plus at least one
   existing workflow; user data directories are never overwritten.

## Patch procedure

Follow the same validation steps without adding capabilities, increment PATCH,
and state in the release notes that no operators or Readers were added. When a
fix accompanies an expansion batch that is not yet released, fold it into the
pending MINOR instead of publishing an interim PATCH.

## Compatibility

- Plugin dependency bounds are generated as `biopipe-studio>=X.Y.Z,<X+1`
  (`biopipe/developer.py`), so a MAJOR increment intentionally rejects plugins
  generated for the previous major line.
- Saved workflows keep their own frozen parameter values and implementation
  pins; a backend version bump alone does not re-pin them.
- Operator and Reader IDs are stable. Removing or renaming an ID is a breaking
  change and must be called out in the release notes.

Historical `v0.x` tags remain as published by the earlier library line; they are
history, not an alternative backend versioning scheme.
