# Post-merge re-verification of stale routes (WSL)

Date: 2026-11-07. Tree: `release/4.x` at `e122cee9` (after merging the
collaborator's Operon 3.0.1 / library 4.0.5 update). Runner:
`scripts/run.py workdir/<route> --memory-mb <budget>` on WSL Ubuntu-24.04,
Python 3.12 (conda `biopipe`).

Every route below was first exercised before the collaborator update, so it is
stale under the release policy and was re-run once here. Results:

| route | steps | status | elapsed (s) | memory budget |
|---|---|---|---|---|
| b1_route | 8 | complete | 0.95 | 4 GB |
| b2_route | 9 | complete | 10.37 | 4 GB |
| b3_route | 8 | complete | 10.80 | 4 GB |
| b4_route | 8 | complete | 0.24 | 4 GB |
| b5_route | 8 | complete | 0.08 | 4 GB |
| b6_route | 8 | complete | 0.70 | 4 GB |
| b7_route | 8 | complete | 0.34 | 4 GB |
| b8_route | 6 | complete | 291.68 | 16 GB |
| b9_route | 8 | complete | 0.04 | 4 GB |
| b10_route | 6 | complete | 0.07 | 4 GB |
| b12_route | 6 | complete | 67.63 | 4 GB |
| b13_route | 6 | complete | 0.70 | 4 GB |
| b14_route | 6 | complete | 2.04 | 4 GB |
| b15_route | 6 | complete | 16.29 | 4 GB |
| b16_route | 10 | complete | 0.77 | 4 GB |
| b17_route | 11 | complete | 0.14 | 4 GB |
| b18_route | 12 | complete | 0.05 | 4 GB |
| b19_route | 4 | complete | 1.00 | 4 GB |
| b20_route | 14 | complete | 2.46 | 4 GB |
| b21_route | 7 | complete | 1.42 | 4 GB |
| b22_route | 8 | complete | 102.99 | 4 GB |
| b23_route | 4 | complete | 4.16 | 16 GB |
| b24_route | 6 | complete | 0.15 | 4 GB |
| b25_route | 3 | complete | 2.38 | 4 GB |
| b26_route | 6 | complete | 1.01 | 4 GB |
| b27_route | 6 | complete | 0.26 | 4 GB |
| b28_route | 11 | complete | 0.10 | 4 GB |
| b29_route | 8 | complete | 0.02 | 4 GB |
| b30_route | 7 | complete | 0.30 | 4 GB |
| b31_route | 8 | complete | 0.04 | 4 GB |
| b32_route | 6 | complete | 1.43 | 4 GB |
| b33_route | 8 | complete | 0.39 | 4 GB |
| b34_route | 8 | complete | 0.01 | 4 GB |
| b35_route | 6 | complete | 1.04 | 4 GB |
| b35_route2 | 6 | complete | 1.07 | 4 GB |
| b36_route | 6 | complete | 1.36 | 4 GB |
| b37_route | 6 | complete | 0.40 | 4 GB |
| b38_route | 6 | complete | 4.36 | 4 GB |
| b39_route | 6 | complete | 3.09 | 4 GB |
| b40_route | 6 | complete | 1.24 | 4 GB |
| b41_route | 6 | complete | 0.68 | 4 GB |
| b42_route | 8 | complete | 37.99 | 4 GB |
| b43_route | 6 | complete | 0.97 | 4 GB |
| b44_route | 6 | complete | 0.24 | 4 GB |
| b45_route | 6 | complete | 2.27 | 4 GB |

Notes:

- `b23_route` and `b8_route` need more than 4 GB of admission budget; with
  4 GB they fail at `full_step_admission` (reservation exceeds managed budget).
  With 16 GB both complete.
- B11's route is stored as `read_preprocessing`; the historical `workdir`
  directory `b11_route` no longer exists, so it is not listed here. The
  library route package itself is unchanged.
- Per the release policy these re-runs are the authoritative stale-route pass
  for the current commit; they will not be re-run again unless the tree
  changes or the user requests a release.
