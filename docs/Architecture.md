# architecture.md

# Architecture

This document describes how BioPipe is organised internally: the layers, the dependency rules between them, the in-memory forms that pipelines exchange, the IO pipeline that converts files into forms, and the orchestration that runs a pipeline.

It is written for contributors and maintainers. Users should start with `guide.md`.

## 1. Overview

BioPipe is layered. Each layer has a single responsibility and depends only on the layers below it.

```text
┌─────────────────────────────────────────────────────┐
│ scripts/                                            │  Entry points
│   init_task.py  run.py  validate_task.py            │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ src/pipelines/                                      │  Domain workflows
│   gwas/                                             │
│     manifest.py  init.py  pipeline.py  steps/       │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ src/orchestration/                                  │  Execution engine
│   context.py  step.py  runner.py  bootstrap.py      │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ src/io/  src/align/  src/qc/                        │  Reusable services
│   readers  writers  align  missing  maf  hwe        │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│ src/core/                                           │  Domain kernel
│   forms/  errors/                                   │
└─────────────────────────────────────────────────────┘
```

Dependency direction is one-way, top to bottom. A module may import from any layer below it. It must never import from a layer above it.

| Layer | May import from |
|---|---|
| scripts | pipelines, orchestration |
| pipelines | orchestration, io, align, qc, core |
| orchestration | core |
| io, align, qc | core |
| core | (nothing internal) |

Violations are considered architectural bugs, not style issues.

## 2. Core kernel — `src/core/`

### 2.1 Forms

A form is a minimal, closed, well-defined data structure that pipelines consume and produce. Readers convert file formats into forms. Writers convert forms back into files. Pipelines never touch raw file formats.

BioPipe defines seven forms. Five are implemented; two are reserved.

| Form | Indexed by | Purpose | Status |
|---|---|---|---|
| GenotypeMatrix | variant × sample | Genotype dosages | Implemented |
| VariantTable | variant | Variant metadata (CHROM, POS, REF, ALT) | Implemented |
| SampleTable | sample | Sample metadata | Implemented |
| Table | row ID | Generic tabular data (phenotype, covariates) | Implemented |
| ResultTable | row ID | Analysis results (association, prediction) | Implemented |
| IntervalTable | interval | Genomic intervals (BED, GTF) | Reserved |
| SequenceReads | sample | Read paths (FASTQ, BAM) | Reserved |

Form design rules:

- Every form is a `@dataclass`.
- Every form exposes `validate()` and raises `ValidationError` on failure.
- Indexes are always IDs, never positional.
- A form does not carry file paths, format-specific details, or presentation data.

### 2.2 SampleIndexed protocol

Any form that has a sample dimension keyed by sample ID implements the `SampleIndexed` protocol:

```python
@runtime_checkable
class SampleIndexed(Protocol):
    sample_ids: np.ndarray
    def subset_samples(self, ids) -> "SampleIndexed": ...
```

This protocol enables form-agnostic alignment: the aligner does not need to know which form it is handling.

Currently implemented by:

- GenotypeMatrix
- Table
- SampleTable

Not implemented by:

- VariantTable (indexed by variant)
- ResultTable (indexed by result row, which may be variant, gene, interval, or sample)

### 2.3 Validation

`validate()` enforces structural invariants:

- Array shapes match ID lengths
- IDs are unique
- Required columns are present
- Enum fields hold allowed values

`PipelineContext.put()` calls `validate()` before registering a form. A malformed form never enters the pipeline.

### 2.4 Errors

All BioPipe exceptions inherit from `BioPipeError`:

| Exception | Raised when |
|---|---|
| ReaderFormatError | File extension is unsupported |
| ReaderSchemaError | Column layout violates the contract |
| ValidationError | A form fails `validate()` |
| PipelineError | A step fails or violates its contract |

Every error message states the expected value and the actual value.

## 3. IO pipeline — `src/io/`

### 3.1 The read entry point

```python
read(path: str, role: str, **kwargs) -> dict[str, Form]
```

- `path` — the file to read.
- `role` — the semantic role of the file. Determines which reader handles it.
- Returns a dictionary mapping form names to form objects.

### 3.2 Roles

| Role | Produces | Returns |
|---|---|---|
| genotype | GenotypeMatrix, VariantTable, SampleTable | `{"genotype", "variant_table", "sample_table"}` |
| phenotype | Table | `{"phenotype"}` |
| covariates | Table | `{"covariates"}` |
| interval | IntervalTable (reserved) | `{"interval"}` |
| reads | SequenceReads (reserved) | `{"reads"}` |

A role is a semantic declaration. `.bed` can be a genotype (PLINK) or an interval (BED); the role disambiguates.

The `Returns` column is the authoritative contract for `read()`. Every reader for a given role must return exactly the keys shown. Readers never add or omit keys silently.

### 3.3 Format detection

Detection is based on the file extension only. No header inspection, no magic bytes, no content sniffing.

Rules:

1. Strip a trailing compression suffix (`.gz`, `.bz2`, `.xz`, `.zst`) if present.
2. Inspect the remaining primary extension.
3. Map the primary extension to a parser key.

```text
genotype.vcf.gz   →  strip .gz  →  genotype.vcf   →  parser: vcf
phenotype.csv.gz  →  strip .gz  →  phenotype.csv  →  parser: csv
```

An unrecognized extension raises `ReaderFormatError` with the full list of supported extensions.

Why extension-only: header sniffing fails on truncated files, remote mounts, and encoding edge cases. Extension-only detection is fast, predictable and easy to reason about.

### 3.4 Reader contract

Every reader:

- Accepts a path and optional keyword arguments.
- Validates column names against a hard-coded contract.
- Constructs one or more forms.
- Calls `validate()` on every form before returning.
- Raises `ReaderFormatError` or `ReaderSchemaError` on failure.

Readers do not silently coerce, rename, or fall back. If the input does not match the contract, the run stops.

### 3.5 Hard-coded column names

Tabular readers require fixed column names.

| Role | Required columns |
|---|---|
| phenotype | `sample_id`, `trait_value` |
| covariates | `sample_id`, followed by any columns |

Why hard-coded: automatic column matching misinterprets data when names collide or drift between versions. Fixed names make failures explicit and reproducible.

### 3.6 Adding a new format

To support a new format:

1. Write a reader module in `src/io/readers/`.
2. Register it in `src/io/registry.py` under the appropriate role and extension.
3. Validate the reader against a golden dataset.

No changes to forms or pipelines are required. See `developer.md`.

## 4. Reusable services

### 4.1 Alignment — `src/align/`

`align_forms(forms, reference)` intersects the sample ID sets of every `SampleIndexed` form and reorders them to match the reference form.

```text
Input:  {"genotype": G, "phenotype": P, "covariates": C}
Call:   align_forms(forms, reference="phenotype")
Output: {"genotype": G', "phenotype": P, "covariates": C'}
```

Non-`SampleIndexed` forms (VariantTable, ResultTable) pass through unchanged.

The aligner has no knowledge of which forms exist beyond whether they implement the protocol. Adding a new sample-indexed form does not require modifying the aligner.

### 4.2 Quality control — `src/qc/`

Reusable operators shared across pipelines.

| Module | Function |
|---|---|
| `missing.py` | `compute_missing_rate`, `filter_by_sample_missing` |
| `maf.py` | `compute_maf` |
| `hwe.py` | `hwe_exact_test`, `compute_hwe_pvalues` |

These are format-agnostic and pipeline-agnostic. They operate on raw arrays or on forms.

## 5. Orchestration — `src/orchestration/`

### 5.1 PipelineContext

The context is the single channel through which steps exchange data.

```python
@dataclass
class PipelineContext:
    config: dict
    task_dir: Path
    out_dir: Path
    proc_dir: Path
    fig_dir: Path
    log_dir: Path
    logger: logging.Logger
    rng: np.random.Generator
    device: str

    forms: dict[str, Form]      # domain objects
    artifacts: dict             # non-form outputs (figures, models, reports)
    metadata: dict              # timings, versions, summaries
```

Rule: steps never call each other. All shared state flows through the context.

Rule: domain results go into `ctx.forms` via `ctx.put()`. Non-form outputs go into `ctx.artifacts`.

### 5.2 Step

A step is the atomic unit of execution.

```python
class Step:
    name: str
    consumes: tuple[str, ...]   # forms that must be present
    produces: tuple[str, ...]   # forms that must be registered on exit

    def run(self, ctx: PipelineContext) -> None: ...
```

`produces` lists mandatory outputs only. Optional forms (e.g. covariates) are written to `ctx.forms` without being declared.

`LoopStep` extends `Step` for iterative workflows (training loops, cross-validation). Reserved for ML pipelines; not used by GWAS.

### 5.3 Runner

`run_pipeline(steps, ctx)` iterates over the step list:

1. Check that every consumed form is present.
2. Run the step.
3. Verify that every declared produced form is registered.
4. Record timing.

On any failure, raise `PipelineError` and abort.

The runner is domain-agnostic. It knows nothing about GWAS.

### 5.4 Bootstrap

`src/orchestration/bootstrap.py` centralises the setup shared by every pipeline:

```python
def bootstrap_context(
    task_dir: Path,
    config: dict,
    pipeline_name: str,
) -> PipelineContext: ...
```

It:

1. Resolves `task_dir` to an absolute path.
2. Creates the standard directory layout (`output/`, `output/figures/`, `processed/`, `logs/`).
3. Builds a logger namespaced as `biopipe.<pipeline_name>` that writes to `logs/run.log` and stderr.
4. Seeds the RNG from `config["runtime"]["seed"]`.
5. Returns a fully initialised `PipelineContext`.

Pipeline classes call `bootstrap_context` and never duplicate this logic.

## 6. Pipelines — `src/pipelines/`

### 6.1 Plugin interface

Each pipeline provides four attributes:

| Attribute | Responsibility |
|---|---|
| `manifest` | Module with `default_manifest()` and `validate_manifest()`. |
| `init` | Module with `init_from_input_dir(task_dir)`. |
| `pipeline` | Module containing the pipeline class. |
| `pipeline_class` | The pipeline class itself. `scripts/run.py` instantiates it; the script never imports a concrete pipeline. |

The pipeline is registered in `src/pipelines/__init__.py`:

```python
class _GwasPlugin:
    manifest = gwas_manifest
    init = gwas_init
    pipeline = gwas_pipeline
    pipeline_class = gwas_pipeline.GwasPipeline

PIPELINES = {"gwas": _GwasPlugin()}
```

`scripts/init_task.py`, `scripts/validate_task.py` and `scripts/run.py` access pipelines only through this registry. No entry point imports a concrete pipeline class directly.

### 6.2 GWAS pipeline

Steps, in order:

| # | Step | Consumes | Produces |
|---|---|---|---|
| 1 | load | — | genotype, phenotype |
| 2 | align | genotype, phenotype | genotype, phenotype |
| 3 | sample_qc | genotype, phenotype | genotype, phenotype |
| 4 | snp_qc | genotype, phenotype | genotype |
| 5 | ld_prune | genotype | — |
| 6 | pca | genotype | — |
| 7 | assoc | genotype, phenotype | association |
| 8 | correction | association | association |
| 9 | clump | genotype, association | — |
| 10 | plot | association | — |
| 11 | metadata | association | — |

Order rationale: variant QC (`snp_qc`) precedes LD pruning and PCA so that pruning and components are computed on the filtered variant set. Monomorphic and low-quality variants would otherwise distort both the correlation structure and the principal components. Association testing uses the same filtered matrix, so removed variants do not dilute the multiple-testing correction.

Each step lives in its own module under `steps/`. Statistical models live under `models/`.

Rule: steps do not import from each other. They only share data through the context.

### 6.3 Manifest

The manifest is the run contract. It is generated by `init_task.py`, edited by the user, validated by `validate_manifest()`, and passed to `run()`.

The manifest declares input paths and parameters. It does not declare column names — those are reader contracts.

## 7. Contracts

Four contracts define the boundaries between components. These are stable APIs. Breaking changes require a version bump.

### 7.1 Form contract

- Each form is a dataclass with documented fields.
- `validate()` raises `ValidationError` on any invariant violation.
- Indexes are IDs, never positions.
- Sample-indexed forms implement `SampleIndexed`.

### 7.2 Reader contract

- Signature: `read_<role>(path, **kwargs) -> dict[str, Form]`
- Every returned form must pass `validate()`.
- Column names are hard-coded.
- Errors use `ReaderFormatError` / `ReaderSchemaError`.
- The returned dict keys match exactly the `Returns` column in §3.2.

### 7.3 Plugin contract

- A pipeline provides `manifest`, `init`, `pipeline`, `pipeline_class`.
- `pipeline_class().run(task_dir: Path)` is the only entry point.
- Steps are listed in `pipeline_class.steps` in execution order.
- Each step sets `name`, `consumes`, `produces`, and implements `run(ctx)`.
- `pipeline_class.name` matches the registry key.
- Directory layout, logging and `PipelineContext` construction are handled by `src.orchestration.bootstrap.bootstrap_context`. Pipeline classes do not duplicate that logic.

### 7.4 Output contract

- Primary results: `output/`
- Intermediate artefacts: `processed/`
- Figures: `output/figures/`
- Logs: `logs/`

`output/run_metadata.json` is mandatory and records pipeline version, dependency versions, full manifest, per-step timings, and QC summaries.

Input file hashes are not yet recorded; see `roadmap.md` v0.2.

## 8. Design decisions in one place

- **Index by ID, not position.** Positional alignment is a silent bug source. Sample and variant IDs are always available and always unique.
- **Extension-only detection.** Header sniffing is fragile. Extensions are stable.
- **Hard-coded column names.** Predictable failure is cheaper than silent misinterpretation.
- **Compression is orthogonal.** `.gz` says nothing about content. Strip it and look at what remains.
- **Form-agnostic alignment.** Any form that exposes `sample_ids` and `subset_samples` participates. Adding a new sample-indexed form requires no aligner change.
- **Steps never call each other.** All shared state goes through the context. This makes every step independently testable and reorderable.
- **Manifest is the run contract.** Code changes are not required to change parameters.
- **One-way dependencies.** scripts → pipelines → orchestration → services → core. No reverse imports.
- **Variant QC before LD pruning and PCA.** LD and principal components are computed on the post-QC matrix, not the raw matrix. Monomorphic and low-quality variants would otherwise distort both.
- **Pipeline bootstrap is centralised.** Directory layout, logging and context construction live in `orchestration/bootstrap.py`. Pipeline classes contain only their step list and manifest handling.

## 9. Extension points

| Goal | Where to extend | Reference |
|---|---|---|
| Support a new input format | `src/io/readers/` + `registry.py` | `developer.md` |
| Add a pipeline step | `src/pipelines/<name>/steps/` | `developer.md` |
| Add a statistical model | `src/pipelines/<name>/models/` | `developer.md` |
| Add a new pipeline | `src/pipelines/<name>/` + register | `developer.md` |
| Add an output writer | `src/io/writers/` | `developer.md` |
| Add a new form | `src/core/forms/` | `developer.md` |
| Extend to ML/DL | Implement `to_tensor`, use `LoopStep` | `roadmap.md` |

## 10. File layout

```text
src/
  version.py
  core/
    errors/
    forms/
      protocol.py
      genotype.py
      variant.py
      sample.py
      table.py
      result.py
  io/
    __init__.py
    detect.py
    registry.py
    readers/
      vcf.py
      plink.py
      table.py
  align/
    align.py
  qc/
    missing.py
    maf.py
    hwe.py
  orchestration/
    context.py
    step.py
    runner.py
    bootstrap.py
  pipelines/
    __init__.py
    gwas/
      manifest.py
      init.py
      pipeline.py
      steps/
      models/
      plot.py

scripts/
  init_task.py
  run.py
  validate_task.py

docs/
  README.md
  guide.md
  input_spec.md
  architecture.md
  developer.md
  roadmap.md
  CHANGELOG.md
```