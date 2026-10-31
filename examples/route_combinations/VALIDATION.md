# Unified v3 integration validation

Validated on 2026-11-01 with Windows, Python 3.11.15 and the unified v3 operator
library. Every execution used a fresh copy in a temporary workspace; all 11 input
files matched the original public-data files by SHA-256 after execution.

| Workflow | Completed steps | Figure sets | Result |
|---|---:|---:|---|
| RefSeq CDS | 11 | 2 | Complete |
| 1000 Genomes chr22 | 13 | 4 | Complete |
| Leukemia ALL/AML | 11 | 3 | Complete |
| PBMC3k | 12 | 6 | Complete |
| QIIME moving pictures | 13 | 4 | Complete |

All 60 steps completed. Each of the 19 figure sets has PNG, PDF and SVG files.
The tests check completed summaries, managed-memory reports and these saved
formats. They do not independently review every biological interpretation or
every plotted point.

## Frozen parameters and Reader dispatch

All five examples and the 16 newly integrated route templates have an independent
`parameters.json`. Source nodes declare an exact registered Reader ID. The
RefSeq example's old `args.reader: fasta` selector was migrated to
`source.reader: FastaReader`; `TxtReader`'s separate parser argument keeps its
existing meaning. Previously shipped templates retain their configuration apart
from explicit Reader disambiguation.

The acceptance coverage comprises five complete executions, five `--check`
preflights, 24 template contract checks, one example-inventory/snapshot check and
four preflight unit tests. The final metadata-only subset passed 34 checks; the
complete executions passed separately. Template checks do not claim that every
template's external dependency or scientific kernel was exercised here.

Preflight uses compiled metadata, including a task's frozen plugin lock when
present. It does not execute Readers or operators. The explicit local CLI can
check declared inputs outside the task directory, such as `../data.csv`; missing
files still fail. Studio and HTTP calls retain their default workspace boundary.

## Memory and streaming evidence

The acceptance run supplied a **512 MiB managed budget** through the CLI. This is
a test setting, not an application limit or a cap on total Python process RSS.
The shipped examples use the normal startup-based automatic budget.

The PBMC3k journal recorded block preparation, 168 `densify_block_spill` events,
source preparation completion and release of prepared source blocks. PCA and the
subsequent full-matrix operators then ran under the normal planner. All workflows
recorded step planning and last-use release events. An earlier 128 MiB PBMC3k run
was correctly refused at full-step admission before PCA because its reservation
could not fit; the failure and memory journal were preserved.

## Environment and interpretation limits

The exercised environment contained NumPy 2.4.6, SciPy 1.17.1, pandas 2.3.3,
scikit-learn 1.9.1, Matplotlib 3.11.2, anndata 0.12.19, h5py 3.16.0 and
umap-learn 0.5.12. These record the test environment; they are not a new dependency
lock or a promise that other versions give numerically identical results.

The original upstream `ANALYSIS.md` files are retained as provenance. Successful
execution is not independent validation of their numerical or biological claims.
In particular, the signed Leukemia expression data can produce undefined
count-style log-fold changes; this example follows rank-test p-values and BH
correction instead. The PBMC3k annotations and ID-derived QIIME subject groups
retain the limitations described in [README.md](README.md).

Local integration evidence is retained under `.tmp/curated-runs-final/`, including
`acceptance.json`, per-copy process logs, step summaries and memory event journals.
These generated files are not part of the shipped input datasets. Reproduce the
checks with:

```text
python -m pytest tests/test_route_combinations.py tests/test_task_preflight.py
```
