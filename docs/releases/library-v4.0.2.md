# Operon Operator Library v4.0.2

**Minimum application:** 2.6.0 (frontend 2.6.0)

This is a documentation and onboarding release. The operator set is unchanged from
v4.0.1: **717 operators, 101 Readers, 7 packages, 24 built-in routes, protocol v3**.
Execution identity, contracts and workflow parameters are identical, so existing
workflows do not need to be repinned.

## What changed

- Added `QUICKSTART.md` (English) and `QUICKSTART.zh.md` (Chinese) at the repository
  root: install `Operon_Setup.exe` 2.6.0, import the operator-library zip through
  **Operator Library → Import package**, and run a real 1MEL/VHH workflow. Both
  documents include an agent prompt that requires reading the documentation and
  inspecting the canvas before any edit, and explicit confirmation before a run.
- Added `examples/quickstart/`: the public inputs (`vhh_1mel.pdb` from RCSB 1MEL,
  `vhh.fasta` derived from its chain A SEQRES) and `vhh_interface.route.json`, a
  six-node graph producing `interface_residues.csv` (88 rows) and
  `liabilities.csv` (10 rows).
- The library release now attaches `Operon-Quickstart-<version>.zip` so a
  setup.exe user can obtain the example and both quickstart documents without a
  source checkout.
- Corrected the stale interface count in `examples/smoke_real_data/README.md` and
  `tests/fixtures/smoke_route/ANALYSIS.md`: the validated result is **88 interface
  residues, 52 core, 36 rim** (the old 99/58/41 was the pre-fix, silently wrong
  value recorded in `docs/releases/v1.119.0.md`).

## Verification

- `vhh_interface.route.json` end to end on the 4.0.0 application tree:
  job complete 4/4; `structure_interface_core` 88/52/36; `sequence_liability_scan`
  10 sites (5 oxidation, 3 isomerization, 2 deamidation); both CSV exports read
  back with the expected columns and row counts.
- Registry: 717 operators / 101 Readers / 7 packages / 24 routes, errors [].
- No operator source, parameter JSON or contract changed in this release.

## Assets

- `Operon-Library-v4.0.2-Linux.operon-library.zip`
- `Operon-Library-v4.0.2-Windows.operon-library.zip`
- `operon_builtin_library-4.0.2-py3-none-any.whl`
- `Operon-Quickstart-v4.0.2.zip`
- `SHA256SUMS.txt`
- `verification-ubuntu-latest.json`, `verification-windows-latest.json`
