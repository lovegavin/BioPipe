# Operon Operator Library v5.0.0

Released: 2026-11-07

## Compatibility

| Item | Value |
| --- | --- |
| Library version | 5.0.0 |
| Minimum application | 3.0.2 |
| Built and verified against | 3.0.2 |
| SDK / protocol | SDK 3.7.0; declarations remain operator protocol v3 (v3.5/v3.6/v3.7 are additive revisions) |
| Operators / Readers | 867 / 108 |
| Packages / builtin routes | 7 / 72 |

Library v5.0.0 is the first release of the renamed project. It declares
operator protocol v3 with SDK 3.7 explicit port formats: 970 of 975
descriptors carry `protocol_revision: "3.7"`, the five polymorphic operators
stay on the supported legacy revision, and the static registry validates all
72 builtin routes.

## What is included

- 867 operators, 108 Readers, 7 packages and 72 builtin routes.
- Three-platform route verification evidence accumulated across the 4.x and
  5.0.0 development cycles (`docs/verification/routes-4.x.md` and the
  `docs/verification/library-*` pages).
- Bilingual quick start (`QUICKSTART.md`, `QUICKSTART.zh.md`) plus the
  `Operon-Quickstart-v5.0.0.zip` example archive.
- Portable builtin route bundles (`Operon-Routes-v5.0.0.zip`).

## Optional SDK revisions

Library 5.0.0 targets Studio 3.0.2 and uses SDK 3.7 explicit port formats.

- 970 of 975 descriptors declare `protocol_revision: "3.7"` with
  `data_formats.inputs/outputs` (862 operators and 107 Readers).
- `analyze_contacts`, `export_results`, `order_axis`, `select` and
  `sequence_stats` remain on the supported legacy revision: their Form/file
  polymorphic ports cannot be expressed without wildcard or union capabilities.
- Mixed graphs stay valid because edge analysis permits a legacy port and
  treats only the declared-to-declared edges strictly. The rule is implemented
  and covered by the protocol test group (73 passed).
- `protocol_version` remains the integer `3`; v3.5 localization remains
  supported by the SDK and is not enabled here because this library ships no
  translated operator corpus.
- Registry verification: 867 operators, 108 Readers, 7 packages, 72 routes,
  0 errors; a six-step representative route completes on the migrated tree.

## Rename and compatibility

The project, Python packages, CLI, desktop application and distribution
artifacts are renamed to Operon. Persisted identifiers that predate the
rename are still accepted on read:

- `biopipe.task-parameters` task parameter snapshots.
- `biopipe.workflow`, `biopipe.workflow-parameters`,
  `biopipe.workflow-execution` and `biopipe.workflow-lock` documents.
- Legacy `.biopipe-library.zip` packages remain selectable in the import
  picker; new packages use `.operon-library.zip`.
- Saved routes and jobs are not rewritten; new files are written with the
  `operon.*` identifier.

## License

Operon and the Operator Library are licensed under the Apache License,
Version 2.0. The repository `LICENSE` and `NOTICE` carry the full text and the
copyright notice; bundled third-party components keep their own licenses in
`THIRD_PARTY_NOTICES/` (frontend dependencies, the LGPL-3.0 pgenlib Windows
runtime, and the Microsoft .NET/WebView2 runtime notices).

The Studio frontend and installer parts of the distribution are owned by the
frontend release; their README license statement and package metadata are being
aligned to Apache-2.0 separately (see
`docs/verification/operon-5.0.0-license-audit.md`). Library bundles produced by
this tag contain the operator sources and packages; the Apache-2.0 terms in the
repository `LICENSE` apply to them.

## Documentation

- [Library 5.0.0 guide](https://github.com/lovegavin/Operon/blob/main/docs/library-v5.0.0.md)
  (packages, reader categories, builtin routes, installation).
- [Three-platform verification](https://github.com/lovegavin/Operon/blob/main/docs/verification/operon-5.0.0-cross-platform.md)
  (WSL, GPU cluster and Windows route values, md5s and suite results).
- [SDK 3.7 compatibility report](https://github.com/lovegavin/Operon/blob/main/docs/verification/operon-5.0.0-compatibility.md)
  and [release-document audit](https://github.com/lovegavin/Operon/blob/main/docs/verification/operon-5.0.0-docs-audit.md).
- [License audit](https://github.com/lovegavin/Operon/blob/main/docs/verification/operon-5.0.0-license-audit.md)
  and [Studio 3.0.2 release-document audit](https://github.com/lovegavin/Operon/blob/main/docs/verification/operon-3.0.2-release-doc-audit.md).

## Assets

| Asset | Notes |
| --- | --- |
| `Operon-Library-v5.0.0-Linux.operon-library.zip` | Linux bundle, verified with application 3.0.2; sha256 `94b2931ca6629c113fbd62d63ce7fc1bbe2129677b8c12f8a1d3bc34d2e49d28` |
| `Operon-Library-v5.0.0-Windows.operon-library.zip` | Windows bundle, verified with application 3.0.2; sha256 `96b0831aa8b158851c46274fb3ef4e941f4a1aa10397cf086b78c447c6876d4f` |
| `operon_builtin_library-5.0.0-py3-none-any.whl` | Portable factory seed wheel; sha256 `c4d21c9ec5485a5b0cc0e1f787b1dc4679a83b4202628d6d70e22818701a5b7f` |
| `Operon-Routes-v5.0.0.zip` | 72 route bundles plus per-route `.operon.zip` files; sha256 `7ef837cf32cf1964e6da164b0598dba401e92b6bc711d8a93aed51697f504c6e` |
| `Operon-Quickstart-v5.0.0.zip` | Bilingual quick start and 1MEL example data; Linux sha256 `772312ad019bffa7422e50c6b4dbb67c81356cdce3ff4f5ab661edd2d903ee57`, Windows sha256 `ec46e0633568ac1b2de11919b0c02667fa8fd55a6ef08d1b93eca135023301cc` |
| `Operon-Library-v5.0.0-Guide.md` | Detailed package, reader and route reference for this release; sha256 `40056f6d1ddb8c518c930edd4eb045853a13f459338da6645bbc48bfea41b04f` |
| `SHA256SUMS.txt` | Checksums for the assets above |
| `verification-*.json` | Install, route-freeze and worker-streaming verification |

## Known issues

- `build_bundle` is not byte-reproducible: repeated builds from identical
  inputs can produce different archive hashes. Verification is performed on
  the produced bundle, not on a hash recorded in advance.
- The Windows bundle must be produced and verified on Windows; the Linux
  runner cannot cross-build it.
- The default test environment pins NumPy 2.5.4 while numba 0.61.0 requires
  NumPy <= 2.1. That combination fails five optional-analysis imports; in the
  dedicated NumPy 2.1.3 environment the full suite is 3,504 passed / 223
  skipped / 0 failed, so this is a host constraint rather than a library
  regression.
- Installer verification exercises dependency readiness with synthetic
  adapters. Real external tools and databases are covered by the
  three-platform route evidence, not by the bundle installer test.

## Verification

- Static registry: 867 operators, 108 Readers, 7 packages, 72 routes,
  0 errors.
- Route verification: 48 operator batches executed on real public datasets
  across WSL, the GPU cluster and Windows, with independent oracles for each
  domain.
- Release verification: application unchanged after install, frozen route
  parameters preserved, idempotent install and worker streaming checks pass.
- Full test suite (release-gating): 3,504 passed, 223 skipped, 0 failed in
  2,338.58 s on Studio 3.0.2 with SDK 3.7.0 and NumPy 2.1.3.
