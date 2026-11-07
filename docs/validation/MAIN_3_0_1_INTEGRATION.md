# Main integration of Operon 3.0.1

## Source and release boundaries

The application implementation from published commit
`db456e9f67a77d53a3ae540ce1272bb859ec83b4` is merged into the author's `main`,
starting at `1257966fb5ca4c5cabc30fc1a80ff402c51c64fe`.

The complete `library/` tree is retained unchanged from that main commit:
`035008ee2bc39fd278ccfb658cf772a87f20dc1e`. This preserves the author's operator
and Reader implementations, helpers, parameter JSON, documentation, generated
indexes, route templates and independent library version. Static discovery finds
849 operators, 107 Readers, seven packages and 66 routes.

The application version is 3.0.1; earlier backend 3.0/4.0 labels from the library
development branch do not set the desktop application version. Historical notes
are preserved separately. The immutable `v3.0.1` tag, Windows installer, Linux
bundle and their tested 2026.11.6.1 library seed are not replaced by this merge.
Updating a source checkout is distinct from installing a newer operator library.

## Preserved fixes and integration adjustments

- Preserve main's isolated-environment proxy declarations and its fallback when
  a named interpreter is unavailable, plus the 20-row remote preview default.
- Preserve the author's frontend icon aliases and library packaging/documentation utilities.
  Extend icon aliases for newly added library names, without editing operators.
- Keep the released lightweight dependency groups, both CLI entry points, viewer
  resources, YAML/script authoring, memory controls and installer fixes.
- Compare an older route through the current graph model before publishing a new
  route version. Missing optional `script`/`adaptation` defaults no longer rewrite
  unchanged library indexes. An actual parameter change still increments the
  route version; old values remain intact. This is a post-release main fix.
- Make the native-artifact receipt regression assertion respect platform line
  endings by checking the byte count of the file actually saved on disk.
- Name `PdbReader` and `FastaReader` explicitly in the reference/quickstart route.
  Adding another Reader for a shared extension must not change the chosen
  interpretation or make a saved example depend on suffix guessing.

## Focused local verification

- Python protocol, isolated execution, agent permissions, format adaptation,
  YAML imports, workflow specifications, readiness, native exports and catalog
  suites: **79 passed, 1 skipped** after resolving temporary-directory access
  issues and correcting the newline-dependent assertion. Only failed cases were
  repeated, rather than rerunning the passing suites.
- Route-index compatibility regressions: **2 passed**. Both unchanged legacy
  serialization and actual parameter changes are covered.
- Reference route validation and example-input checks: **2 passed** after
  making the Reader choice explicit for the expanded library.
- Frontend operator presentation, contracts, refresh, graph, import diagnostics,
  agent bridge and add-operator suites: **45 passed** across seven files. The
  presentation suite was repeated after the icon fix.
- Production frontend TypeScript/Vite build: passed.
- `python -m operon registry check`: no errors and no changed indexes.
- `python scripts/build_operator_docs.py --check`: no changed library pages or indexes.
- Library tree comparison with the author commit: identical.

This is an application/library integration check, not a repeat of all scientific
operators, GUI Setup acceptance, or clean-machine dependency installation.
Previously published installer evidence remains on the 3.0.1 Release page.
The existing Windows/Linux application CI also includes the new route-index
regressions; scientific operator expansion suites remain independently managed.
