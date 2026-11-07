# Operon Operator Library v4.0.4

Quick-start release for the **Operon 2.6.0** desktop application. This release
adds the bilingual quick-start guides to the release assets; it does not change
analysis code.

## Compatibility

- Minimum application: **2.6.0**
- Built and verified against application **2.6.0**
- Protocol: **v3**
- Registry: **717 operators / 101 Readers / 7 packages / 24 routes**, errors `[]`
- Platform: Windows x86_64, Linux x86_64

## What changed

- `QUICKSTART.zh.md` and `QUICKSTART.md` are now published as release assets.
  They cover application installation, library import, agent + MCP setup,
  remote Linux execution, the canvas/CLI path, expected results and
  troubleshooting.
- The guides use the example data already present in the source repository at
  `examples/smoke_real_data/input/` (`vhh_1mel.pdb`, `vhh.fasta`). No data
  archive is attached.
- The release workflow no longer packages a separate quick-start data zip.
- Library version and build metadata are bumped to **4.0.4**.

## Verification

- Library build and independent installation verification run on Windows and
  Linux for application 2.6.0.
- Full offline test suite on the merged application + library tree:
  **2931 passed, 220 skipped, 0 failed**.
- Frontend 2.6.0: **142 tests passed**.
- Desktop API smoke test: demo graph completes 3/3 steps.
- Operator closure coverage: **717/717** (158 real-data runs, 137 synthetic
  contract runs, documented per operator).

## Assets

- `Operon-Library-v4.0.4-Windows.operon-library.zip`
- `Operon-Library-v4.0.4-Linux.operon-library.zip`
- `operon_builtin_library-4.0.4-py3-none-any.whl`
- `QUICKSTART.zh.md`, `QUICKSTART.md`
- `SHA256SUMS.txt`
- `verification-windows-latest.json`, `verification-ubuntu-latest.json`

Install the package matching the platform. A Windows package imported on Linux
is rejected with `Library source does not match wheel`.
