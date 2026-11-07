# Operon Operator Library v5.0.1

**Release date:** 2026-11-08

Patch release for the 5.0 line. It fixes the builtin route release asset: each
builtin route is now published as its own importable workflow bundle
(`<route>.operon.zip`) instead of one collection archive.

## What changed

- **Routes are individual `.operon.zip` bundles.** Studio imports workflow
  bundles one graph at a time (`graph.json`, `parameters.json`, optional
  `execution.json`), so a collection zip was rejected with
  `Workflow bundle must contain graph.json, parameters.json and optional execution.json only`.
  The release now attaches all 72 route bundles as separate assets; their
  checksums are appended to the release `SHA256SUMS.txt`.
- No operator, Reader, route or contract behaviour changed relative to 5.0.0.
  Registry stays at 867 operators / 108 Readers / 7 packages / 72 routes,
  errors 0, and 975 descriptors (970 with explicit SDK 3.7 `data_formats`,
  5 polymorphic legacy operators).

## Compatibility

| Item | Value |
| --- | --- |
| Operon Studio | 3.0.2 |
| Operator protocol | v3 declarations, SDK 3.7 port formats |
| `minimum_application` / `build_application` | 3.0.2 / 3.0.2 |

## Assets

| Asset | Purpose |
| --- | --- |
| `Operon-Library-v5.0.1-Linux.operon-library.zip` | Operator library, Linux |
| `Operon-Library-v5.0.1-Windows.operon-library.zip` | Operator library, Windows |
| `<route>.operon.zip` (72 files) | One importable workflow bundle per builtin route |
| `Operon-Quickstart-v5.0.1.zip` | QUICKSTART pair plus the 1MEL example |
| `operon_builtin_library-5.0.1-py3-none-any.whl` | Factory seed wheel |
| `QUICKSTART.md`, `QUICKSTART.zh.md` | Bilingual quick start |
| `install_dependencies.py`, `install-dependencies.sh`, `install-dependencies.ps1` | Dependency repair helpers |
| `SHA256SUMS.txt` | Checksums for all release assets |
| `verification-ubuntu-latest.json`, `verification-windows-latest.json` | Post-install verification |

## Verification

CI runs on Ubuntu and Windows for the tagged commit: independent-library build,
install into a clean profile, frozen-route and worker checks, and the
verification script. Both jobs must pass before publish. See the two
`verification-*.json` assets for `application`, `library`, `operators`,
`readers`, `idempotent_install` and `worker_streaming` results.

## Known issues

- Bundle bytes are not bit-reproducible across builds (zip timestamps and entry
  order); use the published SHA256SUMS for identity.
- Installer verification uses synthetic external-tool adapters; real
  tool/database runs are covered by the route evidence in
  `docs/verification/`.
- The host scientific Python stack here (NumPy 2.5.4 with numba 0.61) breaks
  five optional single-cell/UMAP tests; the full suite passes (3,504 passed,
  0 failed) in the isolated NumPy 2.1.3 environment recorded in
  `docs/verification/operon-5.0.0-cross-platform.md`.
