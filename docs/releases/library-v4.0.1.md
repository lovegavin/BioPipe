# Operon Operator Library v4.0.1

**Minimum application:** 2.6.0 (frontend 2.6.0)

This release keeps the operator set of Operon Operator Library v4.0.0
(717 operators, 101 Readers, 7 packages, 24 built-in routes, protocol v3) and
raises the declared minimum host to Operon 2.6.0. It is the library build
that accompanies the wave-6 closure verification.

## Coverage

- Contract execution coverage: **717 / 717** operators (100%).
- Evidence: **158 real-data runs**, **137 contract-valid synthetic runs**.
- No remaining coverage blocker.
- Product defects recorded, not worked around in the library:
  `ligandmpnn_side_chain_packing` packed-file glob, ESM-IF masked-region length,
  aromatic-stacking duplicate bond labels, MD rotamer topology line indexing.

`openfold_predict` (30 aa peptide, OpenFold `finetuning_ptm_2.pt`, CPU,
252.7 s) and `rfdiffusion_design` (official RFdiffusion, `Base_ckpt.pt`, CPU,
69.7 s, contig A2-31 on 1MEL chain A) completed after this release was
published; the library assets are unchanged.

See `docs/verification/library-3.0.1-remote.md` §19 and
`docs/verification/biological-issues-4.0.0.md` for evidence and issue details.

## Compatibility

`minimum_application` and `build_application` are both `2.6.0`. Because the
v2.6.0 GitHub release ships a desktop installer but no wheel, the library CI
falls back to building `operon_studio-2.6.0-py3-none-any.whl` from the
`v2.6.0` tag source when the release wheel is unavailable, and verifies the
installed version before building the library. This exception is recorded in
`docs/library_release_standard.md`; a future application release should attach
the wheel so the fallback is no longer used.

## Verification

- Backend full suite on the 4.0.0 application tree: 2931 passed, 220 skipped,
  0 failed (1789.88 s).
- Frontend 2.6.0: 142 tests passed; desktop API smoke job completed 3/3.
- Windows compatibility tree (v2.6.0 application + library 3.0.1 seed):
  registry 717/101/7/24, errors [].
- Library CI (Ubuntu and Windows): build, independent verification and seed
  wheel all green.

## Assets

- `Operon-Library-v4.0.1-Linux.operon-library.zip`
- `Operon-Library-v4.0.1-Windows.operon-library.zip`
- `operon_builtin_library-4.0.1-py3-none-any.whl`
- `SHA256SUMS.txt`
- `verification-ubuntu-latest.json`, `verification-windows-latest.json`
