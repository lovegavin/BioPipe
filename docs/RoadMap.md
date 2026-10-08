# roadmap.md

# Roadmap

This document describes where BioPipe is, where it is going, and what needs to be built next. It is updated as milestones complete.

---

## 1. Current state

BioPipe v0.1.0 ships a working GWAS pipeline end-to-end.

**Implemented**

| Component | Status |
|---|---|
| Core forms (GenotypeMatrix, Table, ResultTable, VariantTable, SampleTable) | Stable |
| IO pipeline (`read(path, role)`) | Stable |
| Readers: VCF, PLINK 1.x, CSV / TSV / Excel / Parquet | Stable |
| Form-agnostic sample alignment | Stable |
| QC operators: missingness, MAF, MAC, HWE | Stable |
| Orchestration: Step, LoopStep, PipelineContext, Runner, bootstrap | Stable |
| GWAS pipeline: 11 steps, end-to-end | Working |
| Manifest generation and validation | Working |
| Run metadata and reproducibility record | Working |
| Multi-pipeline registry (`pipeline_class`) | Stable |

**Not yet implemented**

| Component | Notes |
|---|---|
| Automated test suite | No unit, contract or golden tests committed yet. See §2 v0.2. |
| Additional genotype readers | BGEN, PLINK 2.x `.pgen`, Oxford `.gen` |
| Additional pipelines | Everything below GWAS |
| ML/DL extension points | `to_tensor`, `LoopStep` reserved but not implemented |
| Packaging | Not installable via `pip install` |
| CI | No automated checks on push |

---

## 2. Milestones

### v0.2 — Hardening the GWAS pipeline

**Goal:** make the existing pipeline trustworthy and reproducible.

| Item | Priority |
|---|---|
| Golden test: BioPipe vs PLINK2 on a small dataset | P0 |
| Golden test: BioPipe vs GEMMA for OLS | P0 |
| Golden test: Firth vs R `logistf` | P1 |
| Unit tests for readers, alignment, QC operators | P0 |
| Contract tests for plugins and readers | P1 |
| Fix step ordering: `snp_qc` before `ld_prune` / `pca` | P0 |
| Fix HWE control-group detection for 1/2 phenotype coding | P0 |
| Add MAC lower bound to `snp_qc` | P1 |
| Vectorise `ld_prune` (currently O(n × window) in Python) | P1 |
| Vectorise `assoc` for OLS (matrix form instead of per-SNP loop) | P1 |
| Chunked / memmap backend for large genotype matrices | P1 |
| Input file hashing in `run_metadata.json` | P2 |
| `pyproject.toml` + `pip install -e .` | P2 |
| CI: run tests on push | P2 |

**Exit criterion:** a golden test proves numerical agreement with at least one established tool; the pipeline is installable and reproducible from a clean environment.

### v0.3 — Second pipeline and shared abstractions

**Goal:** validate that the layering holds by building a second workflow.

Candidate second pipelines, in order of preference:

| Pipeline | Rationale |
|---|---|
| Polygenic risk scoring (PRS) | Reuses genotype + phenotype + covariates; adds model fitting |
| Differential expression (bulk RNA-seq) | Exercises `Table` and a new `ExpressionMatrix` form |
| Variant annotation and filtering | Exercises `IntervalTable` (BED, GTF) |

| Item | Priority |
|---|---|
| Add `IntervalTable` form and BED / GTF readers | P0 |
| Add `ExpressionMatrix` form (if RNA-seq is chosen) | P1 |
| Implement one of the pipelines above end-to-end | P0 |
| Refactor common GWAS steps into a shared `src/qc/` and `src/eval/` | P1 |
| Golden test for the new pipeline | P0 |

**Exit criterion:** two pipelines share the same IO, alignment, QC and orchestration layers without duplication.

### v0.4 — Machine learning interface

**Goal:** make BioPipe usable for prediction and model-based analyses.

| Item | Priority |
|---|---|
| `GenotypeMatrix.to_tensor()` — full-matrix and batched modes | P0 |
| `GenotypeMatrix.to_dataloader()` — batched iterator with shuffling | P0 |
| Backend abstraction: numpy / cupy / torch | P1 |
| `LoopStep` implementation with checkpointing and early stopping | P0 |
| Shared `src/eval/` module: cross-validation, permutation, metrics | P0 |
| First ML pipeline: PRS with ridge / elastic net | P0 |
| Report generation: HTML / PDF summary instead of raw TSV | P1 |

**Exit criterion:** an ML pipeline (e.g. PRS) runs end-to-end with cross-validation and produces a reproducible prediction report.

### v0.5 — Deep learning and multi-omics

**Goal:** support model-based and multi-modal workflows.

| Item | Priority |
|---|---|
| Model plugin interface: `fit`, `predict`, `save`, `load` | P0 |
| GPU-aware orchestration (device selection, memory checks) | P1 |
| Multi-modal data loading (genotype + expression + phenotype) | P1 |
| First DL pipeline: sequence-based variant effect prediction or similar | P2 |
| Multi-omics integration pipeline | P2 |

**Exit criterion:** a DL pipeline trains, evaluates and saves a model reproducibly, with the same orchestration used by statistical pipelines.

---

## 3. Backlog

Items not yet assigned to a milestone. Priorities: P0 = blocking, P1 = important, P2 = nice to have.

### IO

| Item | Priority |
|---|---|
| BGEN reader | P1 |
| PLINK 2.x `.pgen` reader | P1 |
| Oxford `.gen` / `.sample` reader | P2 |
| Zarr / HDF5 genotype backend | P1 |
| VCF multi-allelic re-encoding policy | P1 |
| Parquet writer for results | P2 |
| BED and GTF readers | P1 |

### Core

| Item | Priority |
|---|---|
| `GenomeBuild` enum with conversion helpers | P1 |
| `to_memmap` / `to_zarr` on `GenotypeMatrix` | P1 |
| Alembic-style migration notes for form schema changes | P2 |

### Pipelines

| Pipeline | Priority |
|---|---|
| PRS (polygenic risk score) | P0 |
| Differential expression (bulk RNA-seq) | P1 |
| Variant annotation / filtering | P1 |
| CNV calling | P2 |
| Methylation differential analysis | P2 |
| ChIP-seq / ATAC-seq peak analysis | P2 |
| Single-cell RNA-seq | P2 |
| Spatial transcriptomics | P2 |
| Metagenomics | P2 |
| Mendelian randomisation | P2 |
| Colocalisation | P2 |

### ML / DL

| Item | Priority |
|---|---|
| Ridge / elastic-net PRS | P0 |
| Random forest / gradient boosting baselines | P1 |
| Cross-validation harness | P0 |
| Feature importance report | P1 |
| Sequence-based models (CNN, transformer) | P2 |
| Graph neural networks for interaction data | P2 |

### Infrastructure

| Item | Priority |
|---|---|
| `pyproject.toml` and editable install | P1 |
| CI (GitHub Actions: lint, test) | P1 |
| Docker / Singularity image | P1 |
| Conda lockfile (`conda-lock`) | P1 |
| Release automation | P2 |

### Documentation

| Item | Priority |
|---|---|
| API reference (auto-generated) | P1 |
| Tutorial: running GWAS on a public dataset | P1 |
| Tutorial: adding a new reader, step by step | P2 |
| Migration guide for form schema changes | P2 |

### Performance

| Item | Priority |
|---|---|
| Vectorised OLS across all variants (matrix multiplication) | P0 |
| Chunked Firth (process variants in batches, free memory) | P1 |
| Parallel association via multiprocessing or Dask | P1 |
| Sparse matrix support for rare variants | P2 |
| Align PCA missing-value imputation with PLINK2 two-pass method | P1 |

---

## 4. Guiding principles

These are the rules that keep the roadmap coherent. Any new item must not violate them.

1. **Format convergence.** Every input format becomes one of a small set of forms. Adding a format must not require touching pipelines.
2. **One-way dependencies.** `scripts → pipelines → orchestration → services → core`. Never reverse.
3. **ID-based indexing.** Sample and variant alignment is by ID, never by position.
4. **Predictable failure.** Readers and validators fail loudly. No silent coercion, no auto-detection of column names.
5. **Independent steps.** Steps share state only through the pipeline context.
6. **Manifest as contract.** Parameters live in the manifest, not in code.
7. **Two pipelines before abstraction.** A shared abstraction is justified when a second pipeline needs it, not when the first one might.
8. **Reproducibility is non-negotiable.** Every run records enough metadata to be replayed: versions, seeds, config, inputs.

---

## 5. What this project is not

To keep scope honest, the following are explicitly out of scope unless priorities change:

- **A graphical user interface.** BioPipe is a library and command-line framework. A UI, if desired, belongs in a separate project that consumes the API.
- **A workflow engine.** BioPipe executes a fixed step list per pipeline. It is not Airflow, Nextflow or Snakemake and does not aim to be.
- **A variant database.** BioPipe reads files, it does not index or query remote variant servers.
- **A statistical method library.** BioPipe orchestrates established models. New statistical methods are welcome as plugins, but the framework itself does not claim originality in statistics.
- **A general-purpose ML framework.** BioPipe provides the data layer and orchestration for genomic ML. It does not aim to replace PyTorch or scikit-learn.

---

## 6. How to contribute to the roadmap

If you are working on BioPipe and want to propose an item:

1. Check the backlog above. If the item exists, add priority and context.
2. If it is new, add it with a one-line rationale and a priority.
3. If it conflicts with a principle in section 4, raise the conflict before adding it.

The roadmap is a working document. It reflects priorities, not promises.