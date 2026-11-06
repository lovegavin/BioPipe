# BioPipe Operator Library v4.0.0

BioPipe Operator Library 4.0.0 is the operator/Reader release bundled with
BioPipe 4.0.0. It keeps protocol v3 and the `export_results` contract unchanged,
and it can be installed on any host application at or above 2.4.1.

## Contents

- 717 operators, 101 Readers, 7 built-in packages, 24 routes.
- Registry check: 0 errors, 108 warnings (same advisory metadata warnings as
  3.0.x).
- Library version: 4.0.0. Minimum application: 2.4.1 (the release used to build
  and verify the bundle).
- The library is built against the published 2.4.1 wheel, installed with
  `python -I`, and verified on both Windows and Ubuntu before publication.

## Changes since 3.0.1

- Version alignment only: no operator, Reader, contract, parameter or route
  changes. The 3.0.1 fixes below remain the behavioural baseline.
- 3.0.1 fixes carried forward: interface SASA masked by the two partner chains,
  DSSP fixed-column parsing, GTF/GFF column-role aliases, LigandMPNN/Vina native
  file registration, deterministic Vina seeds, ColabFold scores persistence,
  protein molecular weight, RNA fold/cofold/duplex parameters, antismash
  gene/CDS deduplication, assembly launcher on Windows, public SciPy gamma
  functions in limma.
- `estimate_memory` is a classmethod on the ten operators that had drifted.
- Five Form defects fixed: `cox_stuart`, `dca`, `var_model`, `mantel`,
  `nestedness`.
- BGEn dosage decoding now handles four-plane one-hot genotypes.

## Verification

- Backend: 2931 passed, 220 skipped, 0 failed (4.0.0 checkout, 29m49s).
- Frontend: 142 tests passed against the 2.6.0 UI.
- Desktop API: 717 operators and 24 routes served; a demo graph completed
  through `POST /api/jobs`.
- Operator coverage: 715/717 executed in the remote closure wave (156 real,
  137 synthetic); OpenFold and RFdiffusion remain resource-gated.
- Known library defects are recorded in
  `docs/verification/biological-issues-4.0.0.md` and are intentionally not
  patched in this release so workflow semantics stay stable.

## Assets

- `BioPipe-Library-v4.0.0-Linux.biopipe-library.zip`
- `BioPipe-Library-v4.0.0-Windows.biopipe-library.zip`
- `biopipe_builtin_library-4.0.0-py3-none-any.whl`
- `SHA256SUMS.txt`
- `verification-ubuntu-latest.json`, `verification-windows-latest.json`

This release is marked `--latest=false` so it never replaces the BioPipe
application release.
