# Operon 5.0.0 cross-platform verification

Date: 2026-11-07

Scope: Studio 3.0.2 application, SDK 3.7.0, Operon Operator Library 5.0.0.
The library declares 867 operators, 108 Readers, 7 packages and 72 routes; 969
descriptors carry explicit SDK 3.7 port formats, while five polymorphic
operators (`analyze_contacts`, `export_results`, `order_axis`, `select`,
`sequence_stats`) intentionally remain on their supported v3 declaration.

## Environments

| Platform | Python | Application | SDK | Library |
| --- | --- | --- | --- | --- |
| WSL Ubuntu 24.04 | 3.12.14 | 3.0.2 source tree | 3.7.0 | 5.0.0 |
| srv (Linux, Slurm login node) | 3.11.18 | 3.0.2 source tree, same tarball | 3.7.0 | 5.0.0 |
| Windows 11 | 3.12.10 | `operon-studio` 3.0.2 wheel | 3.7.0 | 5.0.0 |

All three platforms ran the same tree, sha256
`7c16afafaf34d5ac2f984438c59ba9a9e9bfae922a6dde1e407c73bc5169eb09`
(`operon_final.tgz`). The route bundle used on srv and Windows was
`f7bf12de0cba8ba357c2b301afde328fc3c58d7125d4cd417885050f3f34f71b`
(`b48_route_final.tgz`).

## Registry

`operon registry check --json` on WSL, srv and Windows:

- operators 867
- readers 108
- packages 7
- routes 72
- errors `[]`

Warnings (139) are the pre-existing "no direct parameter read" class and do not
affect contracts.

## Route: `liftover_intervals`

Six steps: `liftover_intervals` → export, `liftover_variants` → export,
`chain_coverage_summary` → export.

Step results (identical on all three platforms):

| Step | Result |
| --- | --- |
| `liftover_intervals` | 500 intervals, 500 mapped, 0 unmapped |
| `liftover_variants` | 846 records, 806 mapped, 40 unmapped, 0 reverse-complemented |
| `chain_coverage_summary` | 1,278 chains over 93 chromosomes, 2,896,953,941 covered bp |

Timings:

| Platform | intervals | variants | coverage |
| --- | --- | --- | --- |
| WSL | 0.098 s | 0.057 s | 0.071 s |
| srv | 0.150 s | 0.155 s | 0.180 s |
| Windows | 0.090 s | 0.069 s | 0.084 s |

Exported bytes are identical across platforms:

| Artifact | Size | MD5 |
| --- | --- | --- |
| `lifted_intervals.mapped.bed` | 24,500 B | `2d062cf0b782b11ca043a2b2f524525a` |
| `lifted_intervals.unmapped.bed` | 0 B | `d41d8cd98f00b204e9800998ecf8427e` |
| `lifted_variants.mapped.vcf` | 391,359 B | `9e67481a75be782202f4102e56bfa39d` |
| `lifted_variants.unmapped.vcf` | 25,078 B | `0bea829c6ace105255be23e3a2756302` |
| `chain_coverage_summary.csv` | 5,721 B | `7c7150c56a27b0ca7c8224704da28130` |

## Full test suite (WSL)

Command: `pytest -q` on the 5.0.0 tree.

- Default environment (NumPy 2.5.4): 3,499 passed, 5 failed, 223 skipped,
  51 warnings, 1,980.27 s.
- Final run in the dedicated NumPy 2.1.3 environment: **3,504 passed,
  223 skipped, 0 failed**, 43 warnings, 2,338.58 s (39:00). This is the
  release-gating result.

The five failures are environment drift, not library behaviour: the shared
environment carries NumPy 2.5.4 while Numba 0.61 requires NumPy ≤ 2.1, so the
single-cell stack cannot import.

- `tests/test_extension5.py::test_umap_projection`
- `tests/test_extension11.py::test_pca_hvg_and_cell_cycle_operators`
- `tests/test_extension_operators.py::test_scanpy_doublet_and_marker_score`
- `tests/test_extension_routes.py::test_extension_route_runs[single_cell_loom]`
- `tests/test_route_combinations.py::test_route_combination_executes_in_tmp[pbmc3k_single_cell_atlas]`

All SDK 3.7 and format-migration tests pass: `test_format_adaptation`,
`test_static_format_migration`, `test_manifest_v3`, `test_contracts`.

### Environment-gated retest

The five failures above were re-run in a dedicated environment carrying NumPy
2.1.3 with the same Numba 0.61.0 (`/home/gavin/bp-numpy21`, created with
`--system-site-packages` so the rest of the stack stays shared):

`5 passed, 2 warnings in 170.17 s`

Together with the main run this accounts for 3,504 passing tests with no
library-level failure; the only outstanding failure mode is the NumPy/Numba
pin in the shared environment.

## Release bundles

Both platform bundles were assembled with an installed Studio 3.0.2 (never a
source checkout) and validated with `scripts/verify_library_release.py`;
both verification records report `passed: true`.

| Asset | Size | SHA256 |
| --- | --- | --- |
| `Operon-Library-v5.0.0-Linux.operon-library.zip` | 24,713,713 B | `94b2931ca6629c113fbd62d63ce7fc1bbe2129677b8c12f8a1d3bc34d2e49d28` |
| `Operon-Library-v5.0.0-Windows.operon-library.zip` | 24,714,065 B | `96b0831aa8b158851c46274fb3ef4e941f4a1aa10397cf086b78c447c6876d4f` |
| `Operon-Routes-v5.0.0.zip` | 200,374 B | `7ef837cf32cf1964e6da164b0598dba401e92b6bc711d8a93aed51697f504c6e` |
| `Operon-Quickstart-v5.0.0.zip` (Linux) | 96,151 B | `772312ad019bffa7422e50c6b4dbb67c81356cdce3ff4f5ab661edd2d903ee57` |
| `Operon-Quickstart-v5.0.0.zip` (Windows) | 96,151 B | `ec46e0633568ac1b2de11919b0c02667fa8fd55a6ef08d1b93eca135023301cc` |
| `operon_builtin_library-5.0.0-py3-none-any.whl` | 4,923,983 B | `c4d21c9ec5485a5b0cc0e1f787b1dc4679a83b4202628d6d70e22818701a5b7f` |

## Notes and limitations

- The srv run used the shared verification virtual environment with
  `PYTHONPATH` pointing at the tree; the Windows run used a 3.0.2 virtual
  environment and the same tree.
- The NumPy/Numba drift affects only the five single-cell tests listed above;
  it is not caused by SDK 3.7 or the rename.
- Library bundles are not byte-reproducible across rebuilds; the hashes above
  identify the published artifacts.
- Five polymorphic operators remain on their supported v3 declaration because
  a static port format would narrow their real contract; route validation
  treats edges that touch such a port as unconstrained rather than
  incompatible.
