# Operon Operator Library 2026.11.5

This is an independent library release, not an application/EXE update.
It contains 716 operators and 101 Readers across seven provider packages.
The minimum supported application for the native library bundles is 2.0.4.

Added upstream genome adapters: `amrfinder_plus`, `antismash_bgc`,
`assembly_stats`, `crispr_array_detect`, `flye_assemble`, `rfam_scan` and
`trnascan_se`. Their tool declarations and adjacent documentation are included.
External binaries, databases and optional model downloads are not embedded in
the library archive; check each operator's dependency/resource status before use.

Choose the Windows or Linux `.operon-library.zip` matching the application host
and install it through Library Management or the CLI. Updating the library does
not require reinstalling Studio. Disabled providers and frozen workflow values
are preserved. See [Library release instructions](../library_releases.md).

Administrators preparing a Operon 2.3.0 or later installation may instead install
the separate, platform-independent `operon_builtin_library` seed wheel. It
contains the factory sources, declarations, environment recipes and routes; it
does not replace profile-owned provider versions.

Native bundle verification runs against the released 2.0.4 engine on Windows
and Linux. The attached platform reports cover installation, repeated updates,
existing pins and frozen values, disabled providers and synthetic worker execution.
Native execution of all optional tools and databases is outside that coverage.
