# BioPipe

BioPipe is a local bioinformatics pipeline engine with a visual desktop workspace, typed data contracts, bounded resource planning and an extensible operator SDK. Create branched workflows, reuse saved routes as operators, and connect your own AI agent through CLI or MCP. BioPipe itself does not supply an AI service.

The project has two halves. The upstream Python engine is documented below from the **Engine reference** section onward. The downstream Studio workspace, plugin SDK, resource runtime and agent interface are documented from the **Start Studio** section up to the engine reference. Upstream and downstream have independent release cycles and changelogs.

- Upstream changelog: `docs/changelog/upstream/`
- Downstream release notes: `docs/releases/`

Download the ready-built Windows desktop package from GitHub Releases. Extract the complete ZIP, configure a Python environment as described in its `START_HERE.txt`, then double-click `BioPipe Studio.exe`. Python and analysis dependencies are not bundled. The repository contains development source; compiled desktop distributions are release attachments.

---

## Start Studio

Studio 0.2.0 preserves the upstream Python Steps, Readers and YAML tasks, with 31 built-in operators, 13 readers and four reusable route templates: GWAS, RNA-seq DE, Proteomics DE and survival analysis.

Use Python 3.11+ (tested with 3.12). Build the frontend with Node 22.12+:

```text
python -m venv .venv
# Activate .venv using your shell's standard activation command.
python -m pip install -e ".[agent,dev]"
cd frontend
npm install
npm run build
cd ..
python scripts/studio.py
```

Open <http://127.0.0.1:8765>. The generated CSV demo runs immediately. Format-specific dependencies are listed in `requirements-readers.txt`; DESeq2 and survival analyses use `requirements-analysis.txt`. Dependencies can also be installed with `uv`.

On Windows, a built desktop distribution starts by double-clicking `dist/BioPipe Studio/BioPipe Studio.exe`. The host bundles the frontend and backend startup logic. Python, the backend source and analysis dependencies remain separate. See **desktop setup and portability**.

Both desktop and development entry points use `~/.biopipe/studio` by default. `BIOPIPE_STUDIO_HOME` or `--profile-dir` selects another shared profile; `--workspace` explicitly isolates a workspace. CLI and MCP use the same resolver. No developer username, installation drive or fixed backend port is embedded.

### Extend and automate

```text
biopipe plugin init ./lab_scale
biopipe plugin check ./lab_scale
biopipe plugin test ./lab_scale
biopipe plugin build ./lab_scale
biopipe plugin install ./lab_scale/dist/lab_scale-0.1.0-py3-none-any.whl
biopipe sessions list
biopipe context get
biopipe mcp
```

New plugins use the stable `biopipe_sdk` imports, JSON Schema parameters, explicit info/axis contracts and standard Python entry points. Wheel installation updates the JSON registry while Studio is open. Saved graphs and running jobs retain their plugin version pins. Start with the 30-minute SDK tutorial.

Agents read semantic selection context and issue revision-checked edit batches. Each batch is visible immediately and creates one undo entry. Execution is a separate action; MCP requires `--allow-run` for it. The Agent panel also provides copyable selection context and client revocation. See CLI/MCP setup.

### Downstream Documentation

| Guide | Contents |
|---|---|
| Operator protocol | Descriptor, parameters, ports, outputs, versions and compatibility |
| SDK quickstart / reference | Operator and reader templates, testing and public Python APIs |
| Plugin lifecycle | Hot installation, dependency isolation, pins and migration |
| Agent interface | CLI, MCP, context, atomic commands, permissions and events |
| Data contracts | Static compatibility, runtime checks and metadata propagation |
| Reusable routes | Save/register separation, nested graphs and version snapshots |
| Studio interaction | Canvas editing, panels, results and visual design |
| Resource runtime | Fixed budget, admission, spill, cache format and limits |
| Desktop / portability | Build, launch, profiles and moving computers |

### Downstream Validation

```text
python -m pytest -q
cd frontend
npm test
npm run build
```

Install the `agent` and `dev` extras for the complete suite. Tests cover actual plugin wheels/workers, reader dispatch, plugin upgrade/removal, route compatibility, CLI processes, MCP stdio, revision conflicts, shared undo and data propagation. Windows desktop verification is available in `scripts/verify_desktop.py`.

The resource budget is chosen once before a run. Actual sizes refine step admission; emergency spill protects evictable data. It cannot preempt an active native allocation. New SDK plugins currently execute in full-memory mode; built-in `describe` retains its real chunk implementation. CUDA kernels and a generic chunk SDK are future work.

---

## Engine reference

The engine section below documents the upstream Python implementation. New external extensions should follow the SDK guides above; the YAML engine and its built-in operators are covered here.

A declarative, plugin-based bioinformatics pipeline framework.

BioPipe writes task workflows in `task.yaml`, reads external files into unified `Form` objects, and applies pluggable `Step` operators to filter, compute statistics, model, and plot those `Form` objects. The core goals are: **format and algorithm decoupling, label alignment safety, traceable outputs, zero-registration extensibility**.

Repository: <https://github.com/lovegavin/BioPipe>

Engine changelog: `docs/changelog/upstream/`.

### Engine Table of Contents

- Engine version 2 summary
- Engine Features
- Engine Quick Start
- Core Architecture: Four Protocols
- Runtime: Context and Runner
- Built-in Readers
- Built-in Steps
- End-to-End Pipelines
- Operator Demos
- Output Structure
- Extension Guide
- Design Principles
- Engine Directory Structure
- Engine Development and Testing
- Engine License

---

### Engine version 2 summary

Upstream v2 expands the engine from a GWAS-focused operator set into a general pipeline framework serving five classical analysis paths: bulk RNA-seq DE, proteomics DE, survival analysis, single-cell, and microbiome.

- 28 new built-in Steps across filtering, transformation, statistical modeling, dimensionality reduction, diversity, distance, survival, and visualization.
- 1 new Reader (`TxtReader`) and a new `sep` parameter for `CsvReader`.
- Multi-group comparison integrated into `compare_groups`. Two-group mode is the default and remains fully backward compatible.
- Encoder contract tightened: matrix Readers no longer declare whole-dimension encoders.
- Five end-to-end pipelines and one demo task per operator.

Full history: `docs/changelog/upstream/v2.md`.

---

### Engine Features

- **Declarative orchestration**: describe "what to read, in what order to do what" in YAML.
- **Plugin Readers**: adding a new file format only requires a new module, no registry changes.
- **Plugin Steps**: adding a new operator only requires a new module, auto-discovered.
- **Unified Form model**: all data is an N-dimensional tensor with named dimensions, labels, and info.
- **Complete label coverage**: every axis position must have a label; filtering, merging and alignment never lose positions.
- **Axis-parallel metadata sync**: `axis_info` guarantees that arrays such as chromosome and position are trimmed together with axis subsets.
- **Full export**: every Step's complete result is written to `output/steps/`, with a run index in `run_summary.*`.
- **Explicit error hierarchy**: `BioPipeError` with `ReaderError`, `ManifestError`, `StepError`, `ValidationError`, `ContextError`.
- **Classical backends**: statistical tests delegate to `scipy`, `statsmodels`, `lifelines`, and `pydeseq2`. No statistical model is re-implemented.

---

### Engine Quick Start

#### Environment Setup

Python 3.11+ is required. Conda is recommended.

#### Install Dependencies

**Option 1: Conda (recommended)**

```bash
git clone https://github.com/lovegavin/BioPipe.git
cd BioPipe
conda env create -f environment.yml
conda activate biopipe
```

`environment.yml` declares a portable CPU environment for the engine. It has no machine-specific prefix, local build paths, or mandatory CUDA toolchain.

**Option 2: pip**

```bash
git clone https://github.com/lovegavin/BioPipe.git
cd BioPipe
pip install -r requirements.txt
```

`requirements.txt` installs the engine through portable package requirements — supported version ranges, not a platform-specific lock.

CSV, text, FASTA and MTX support is included. Install `requirements-readers.txt` for the additional Parquet, AnnData, PLINK, BGEN, and VCF Readers, or install only the packages for the formats you use. Native Reader dependencies must be available for the target OS; they are loaded only when that format is used.

Some Steps require optional analysis dependencies:

| Step family | Package source |
|---|---|
| `compare_groups(method=deseq2)` | `requirements-analysis.txt` |
| `kaplan_meier`, `logrank_test`, `cox_regression` | `requirements-analysis.txt` (lifelines) |
| `reduce(method=umap)` | `pip install umap-learn` |
| `reduce(method=tsne)`, `cluster_axis(method=kmeans)` | `pip install scikit-learn` |
| `cluster_axis(method=louvain)` | `pip install networkx` |

#### Write task.yaml

Create `task.yaml` in the task directory. The following minimal example reads a CSV and prints its description:

```yaml
name: csv_demo

sources:
  data:
    path: input/test_party_1.csv
    dims: [sample, feature]
    labels:
      sample: auto
      feature: builtin

steps:
  - name: describe
    inputs: [data]
```

This example comes from `tasks/csv_demo/task.yaml`. It demonstrates the three most basic things: declaring a source, specifying label rules, and invoking the `describe` Step.

#### Run

```bash
python scripts/run.py tasks/csv_demo
```

#### Output Overview

After a run, the task directory contains:

```text
output/
  run_summary.json
  run_summary.txt
  steps/
    01_describe.json
  figures/
```

- `run_summary.json`: machine-readable run index with step names, timings, inputs, parameters, export paths.
- `run_summary.txt`: human-readable run index.
- `steps/*.json`: full export of each Step.
- `figures/*`: images produced by plotting steps.

---

### Core Architecture: Four Protocols

BioPipe is four protocols/contracts plus two runtime components. The four protocols are the heart of the project; understanding them means understanding the whole framework.

| Protocol | Defined in | Question it answers | Key interface |
|---|---|---|---|
| **Manifest** | `task.yaml`, `src/task/manifest.py` | What to read? In what order to do what? | `sources`, `steps`, `labels`, `args`, `params` |
| **Reader** | `src/reader/base.py` | How does a file become a Form? | `extensions`, `requires_siblings`, `excludes_siblings`, `handles_compression`, `read()` |
| **Step** | `src/task/step/base.py` | How is a Form processed? | `name`, `inputs_arity`, `outputs`, `run()`, `export()` |
| **Form** | `src/core/forms/form.py` | What does the data look like? | `data`, `dims`, `labels`, `info`, `axis_info`, `validate()`, `subset_axis()` |

Runtime components:

- **Context**: holds `forms`, `params`, `step_params`, `metadata`, `artifacts`; manages output directories; writes `run_summary.*` at the end.
- **Runner**: executes steps in order, resolves inputs, checks outputs, writes per-step JSON.

In one sentence: **Manifest orchestrates, Reader ingests, Step processes, Form unifies, Context/Runner runs.**

---

#### Protocol 1: Manifest Task Protocol

The Manifest is the declarative orchestration layer. Users only write YAML, no Python.

**Top-level structure**

```yaml
name: my_task
sources:
  ...
steps:
  ...
```

Optional top-level `params` is read by `Context` as task-level parameters.

**sources specification**

Each source is a mapping:

```yaml
sources:
  my_data:
    path: data/example.vcf
    dims: [variant, sample]
    labels:
      variant: builtin
      sample: auto
    args:
      some_option: value
```

- `path`: file path, relative to the task directory.
- `dims`: list of dimension names, must be a non-empty list.
- `labels`: label rules, optional, must be a mapping.
  - Keys must be dimension names in `dims`.
  - Rules support:
    - `"builtin"`: use the format's built-in identifiers.
    - `"auto"`: use positional indices `"0"`, `"1"`, ...
    - `{name: pos, ...}`: explicit mapping.
    - `None`: equivalent to omitted.
- `args`: extra arguments passed to the Reader, optional, must be a mapping.
- Unknown keys are not allowed.

**steps specification**

Each step is a mapping:

```yaml
steps:
  - name: maf
    inputs: [my_data]
    params:
      dim: variant
      threshold: 0.01
      output: filtered
  - name: describe
    inputs: [filtered]
```

- `name`: Step name, must be found in `STEPS`.
- `inputs`: list of input Form names, optional.
- `params`: parameters passed to the Step, optional, must be a mapping.
- Unknown keys are not allowed.

**Execution flow**

Runner executes in order:

1. Look up the Step class by `name`.
2. Check `inputs_arity` against `inputs` length.
3. Resolve input Forms from the Context.
4. Set `ctx.step_params`, inject `_input_names`.
5. Call `step.run(ctx, forms)`.
6. Verify that all declared `outputs` are registered.
7. Call `step.export(ctx)` and write `output/steps/NN_name.json`.
8. Record timings and metadata.

---

#### Protocol 2: Reader Protocol

The Reader is the input adaptation layer, converting heterogeneous files such as FASTA, VCF, BED, CSV, H5AD, PLINK, and BGEN into a unified `Form`.

**Base class contract**

```python
class Reader(ABC):
    extensions: ClassVar[list[str]] = []
    requires_siblings: ClassVar[list[str]] = []
    excludes_siblings: ClassVar[list[str]] = []
    handles_compression: ClassVar[bool] = False

    def matches(self, path: Path) -> bool:
        ...

    @abstractmethod
    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        ...
```

- `extensions`: extensions this Reader handles.
- `requires_siblings`: required sibling files, e.g. PLINK `.bed` requires `.bim`, `.fam`.
- `excludes_siblings`: do not match when these siblings are present, e.g. BED Reader excludes `.bim/.fam/.pgen`.
- `handles_compression`:
  - `False`: the framework decompresses to a temp file first; the Reader only sees a plain file.
  - `True`: the Reader handles compression itself, or needs the original path and same-directory siblings.

**Routing and auto-discovery**

`src/reader/__init__.py` scans the `src.reader.readers` package:

- Imports each module.
- Finds `Reader` subclasses.
- Instantiates them and adds to `READERS`.
- New Readers only need a new module; no registry change.

`read_source(path, dims, labels, **args)` is the unified entry:

1. Calls `pick_reader(path)` to select the unique matching Reader.
2. If the Reader does not handle compression, decompresses to a temp file via `_decompressed`.
3. Calls `reader.read(...)`.

**Label rules**

Label rules per dim support:

- `"builtin"`
- `"auto"`
- `{name: pos, ...}`
- When omitted, the specific Reader decides the default.

Duplicate labels are handled by `unique_labels`; the second occurrence gets `#<position>` appended.

**Encoding and info**

Two kinds of encoders exist in the framework, distinguished by where they apply:

- **Column encoders** — used by wide-table Readers (CSV, BED, GFF3, GTF, Parquet). A single column is a string variable; the encoder is recorded under `info["encoders"][dim][column_label]`. The column label must appear in `form.labels[dim]`.
- **No encoders at all** — matrix Readers (MTX, FASTA, VCF, PLINK, BGEN, H5AD) treat the whole axis as one categorical dimension. Positions along the axis are identified by their row/column index, and the label map already encodes every position. Matrix Readers do not create encoders.

`info` typically contains `missing_code`, usually `np.nan`. Genotype Readers also write `ploidy`, `chrom`, `pos`, etc. If an info entry is parallel to an axis, it must be declared in `axis_info`; `Form.subset_axis` then trims those arrays in sync.

---

#### Protocol 3: Step Protocol

Step is the operator layer. Filtering, selection, merging, transposition, normalization, group comparison, PCA, regression, HWE, MAF, LD pruning, plotting — all are pluggable Steps.

**Base class contract**

```python
class Step(ABC):
    name: ClassVar[str] = "unnamed"
    inputs_arity: ClassVar[int | str] = 0
    outputs: ClassVar[list[str]] = []

    @abstractmethod
    def run(self, ctx: Context, inputs: list[Form]) -> None:
        ...

    def export(self, ctx: Context) -> dict:
        return {}
```

- `name`: step name, matched against `name` in the manifest.
- `inputs_arity`:
  - Integer: fixed number of inputs.
  - `"*"`: any non-empty number of inputs.
- `outputs`: keys that will be registered in the Context; Runner checks them.
- `run`: executes the step.
- `export`: returns a JSON-serializable complete result; Runner writes it to `output/steps/`.

**Parameters and outputs**

- Parameters are read from `ctx.step_params`.
- Runner injects `ctx.step_params["_input_names"]`.
- Steps register outputs via `ctx[out_name] = Form(...)`.
- `Context.__setitem__` automatically calls `form.validate()`.

**Auto-discovery**

`src/task/step/__init__.py` scans `src.task.step.steps`:

- Imports modules.
- Finds `Step` subclasses.
- Requires `name != "unnamed"`.
- Builds `STEPS[name] = class`.
- Duplicate names raise an error.

**Error handling**

- Input, parameter, and execution errors should raise `StepError`.
- Some Steps have explicit failure policies, e.g. `regress` only skips known non-fittable cases.

---

#### Protocol 4: Form Data Protocol

Form is the shared language between Readers and Steps.

```python
@dataclass
class Form:
    data: np.ndarray
    dims: list[str]
    labels: dict[str, dict[str, int]] = field(default_factory=dict)
    info: dict = field(default_factory=dict)
    axis_info: dict[str, list[str]] = field(default_factory=dict)
```

**Constraints**

- `len(dims) == data.ndim`.
- `dims` must not contain duplicates.
- Every dim must have labels.
- Every axis position must be covered by at least one label.
- Label positions must be int and within `0..size-1`.
- Each key listed in `axis_info[dim]` must exist in info and have length equal to the axis size.
- `subset_axis` trims data, labels, and axis-parallel info in sync.
- `get_parallel(field, dim)` retrieves a data column by label, or an info array by `axis_info`.

**Main methods**

- `axis(name)`: returns the axis index.
- `get_parallel(field, dim)`: retrieves the parallel array.
- `subset_axis(dim, indices)`: subsets along a dim.
- `validate()`: structural validation.

---

### Runtime: Context and Runner

**Context**

Location: `src/task/context/base.py`

Responsibilities:

- Holds `forms`, `params`, `step_params`, `metadata`, `artifacts`.
- Manages `out_dir`.
- `__setitem__` automatically calls `form.validate()`.
- `finalize()` writes `output/run_summary.json` and `output/run_summary.txt`.

**Runner**

Location: `src/task/runner.py`

Responsibilities:

- Executes steps in order.
- Checks `inputs_arity`.
- Resolves inputs from the Context.
- Sets `ctx.step_params`.
- Executes `step.run()`.
- Checks `step.outputs`.
- Calls `step.export()` to write `output/steps/NN_name.json`.
- Records timings and metadata.

---

### Built-in Readers

| Reader | Extensions | Main layout | Notes |
|---|---|---|---|
| FastaReader | `.fasta` `.fa` `.fna` `.faa` | sequence × position | Nucleotide/protein sequences, NaN-padded |
| H5adReader | `.h5ad` | obs × var | AnnData, supports layers |
| Gff3Reader | `.gff` `.gff3` | row × 9 columns | GFF3 annotation |
| GtfReader | `.gtf` | row × 9 columns | GTF annotation |
| VcfReader | `.vcf` `.vcf.gz` | variant × sample | GT to ALT count |
| BedReader | `.bed` | row × column | UCSC BED, 3–12 columns |
| CsvReader | `.csv` | row × column | Header supported, `sep` parameter |
| ParquetReader | `.parquet` | row × column | Column names from metadata |
| MtxReader | `.mtx` | gene × cell | 10x MEX |
| Plink1Reader | `.bed` + `.bim` + `.fam` | variant × sample | PLINK 1.x |
| Plink2Reader | `.pgen` + `.pvar` + `.psam` | variant × sample | PLINK 2.x |
| BgenReader | `.bgen` | variant × sample | Expected ALT dosage |
| TxtReader | `.txt` `.tsv` `.tab` | delegated | Delegates to another Reader via `reader` arg (default `csv`) |

---

### Built-in Steps

Every Step is domain-agnostic: it operates on any `Form` whose dimensions match its parameters. Steps are grouped by purpose.

**Data inspection**

- `describe` — print and export a summary of one input form.

**Dimension and label**

- `transpose` — reorder the axes of a form.
- `rename_dim` — rename a single dimension.
- `select` — keep only the listed labels along one dimension.
- `drop` — remove named labels from one dimension.
- `concat` — concatenate several forms along one dimension.
- `attach_info` — attach axis-parallel info arrays from one form to another, aligned by label.
- `join` — attach selected columns from a second form to the first, aligned by label.
- `aggregate` — collapse rows into groups using a group column.

**QC filtering**

- `filter_min` — drop positions whose value doesn't reach a threshold in enough samples.
- `filter_by` — drop positions using rules defined on a second form.
- `missing` — filter positions by missing rate.
- `maf` — filter positions by minor allele frequency.
- `hwe` — filter positions by Hardy–Weinberg exact test.
- `ld_prune` — prune positions by pairwise LD.

**Transformation**

- `normalize` — scale along one axis. Methods: `cpm`, `total`, `median_of_ratios`, `quantile`, `zscore`.
- `log_transform` — `log_base(x + pseudocount)` elementwise.
- `impute` — fill missing cells. Methods: `min`, `median`, `mean`. Works on N-dimensional input.
- `bin` — discretize a continuous axis into quantile or uniform bins.

**Dimensionality and ranking**

- `pca` — principal component analysis of a 2D form (kept for backward compatibility).
- `reduce` — general dimensionality reduction. Methods: `pca`, `umap`, `tsne`, `pcoa`.
- `reduce_axis` — collapse one axis into a statistic: `sum`, `mean`, `std`, `var`, `min`, `max`, `median`, `nonzero`, `count`.
- `rank_axis` — rank positions along an axis and keep the top N by a statistic.
- `cluster_axis` — cluster positions along an axis. Methods: `kmeans`, `hierarchical`, `louvain`.

**Statistical modeling**

- `compare_groups` — group comparison along one dimension of a form. Modes: `two_groups` (default), `one_vs_rest`, `pairwise`. Methods: `ttest`, `welch`, `mannwhitney` (alias `wilcoxon`), `deseq2`.
- `regress` — multiple regression over one dimension of a wide form.
- `correction` — multiple-testing correction: `bonferroni` or `fdr`.

**Diversity and distance**

- `diversity` — per-position diversity metrics: `shannon`, `simpson`, `richness`, `evenness`, `gini`.
- `distance_matrix` — pairwise distances: `euclidean`, `manhattan`, `cosine`, `correlation`, `braycurtis`, `jaccard`, `hamming`.
- `correlation` — pairwise correlations: `pearson`, `spearman`, `kendall`, `cosine`, `jaccard`, `overlap`.
- `permanova` — permutation-based multivariate analysis of variance on a distance matrix.

**Survival analysis**

- `kaplan_meier` — Kaplan–Meier survival curves grouped by a label column.
- `logrank_test` — log-rank test across groups (overall and optional pairwise).
- `cox_regression` — Cox proportional hazards model.
- `forest_plot` — forest plot of hazard ratios.

**Plotting**

All plotting steps write to `output/figures/<filename>` and do not modify the Context.

- `histogram` — histogram of one labeled column.
- `scatter` — scatter plot of two labeled columns.
- `line` — line plot of one column against another.
- `manhattan` — genome-wide Manhattan plot.
- `volcano` — volcano plot of log2FC vs −log10(P).
- `ma_plot` — MA plot.
- `heatmap` — matrix heatmap with optional row selection, standardization, and clustering.
- `boxplot` — box plot of a value column split by groups.
- `violin` — violin plot of a value column split by groups.
- `dotplot` — dot plot of features × groups (value = color, proportion = size).
- `barplot` — stacked bar plot of a composition matrix.

Full parameter references for every Step are in the source files under `src/task/step/steps/`. Each module docstring documents its parameters.

---

### End-to-End Pipelines

Six complete pipelines are shipped as demonstration tasks. Each downloads real public data and runs end to end.

| Task | Path | Data |
|---|---|---|
| Bulk RNA-seq DE | `tasks/rnaseq_de_demo` | airway (GSE52778) |
| Proteomics DE | `tasks/proteomics_de_demo` | CPTAC BRCA |
| Survival analysis | `tasks/survival_demo` | TCGA BRCA |
| Single-cell | `tasks/scrnaseq_demo` | 10x PBMC 3k |
| Microbiome | `tasks/microbiome_demo` | COMPASS-DOE 16S |
| GWAS | `tasks/gwas_demo` | synthetic VCF + phenotype |

Run any of them with:

```bash
python scripts/run.py tasks/<name>
```

---

### Operator Demos

Each operator has a dedicated demo task under `tasks/<operator>_demo/`. The demo reads real data, runs the operator in a minimal pipeline, and produces a JSON export plus optional figures.

| Demo | Operator |
|---|---|
| `csv_demo` | `describe` |
| `filter_min_demo` | `filter_min` |
| `normalize_demo` | `normalize` |
| `log_transform_demo` | `log_transform` |
| `impute_demo` | `impute` |
| `compare_groups_demo` | `compare_groups` (including multi-group) |
| `volcano_demo` | `volcano` |
| `ma_plot_demo` | `ma_plot` |
| `heatmap_demo` | `heatmap` |
| `boxplot_demo` | `boxplot` |
| `reduce_axis_demo` | `reduce_axis` |
| `filter_by_demo` | `filter_by` |
| `rank_axis_demo` | `rank_axis` |
| `reduce_demo` | `reduce` (pca / umap / tsne) |
| `reduce_pcoa_demo` | `reduce(method=pcoa)` |
| `cluster_axis_demo` | `cluster_axis` |
| `dotplot_demo` | `dotplot` |
| `violin_demo` | `violin` |
| `diversity_demo` | `diversity` |
| `distance_matrix_demo` | `distance_matrix` |
| `permanova_demo` | `permanova` |
| `correlation_demo` | `correlation` |
| `join_demo` | `join` |
| `aggregate_demo` | `aggregate` |
| `bin_demo` | `bin` |
| `barplot_demo` | `barplot` |
| `kaplan_meier_demo` | `kaplan_meier` |
| `logrank_test_demo` | `logrank_test` |
| `cox_regression_demo` | `cox_regression` |
| `forest_plot_demo` | `forest_plot` |

---

### Output Structure

```text
output/
  run_summary.json          # machine-readable run index
  run_summary.txt           # human-readable run index
  steps/
    01_step_name.json       # full export of each Step
    02_step_name.json
    ...
  figures/
    *.png                   # outputs of plotting steps
```

- `run_summary.json`: step names, timings, inputs, parameters, export paths.
- `run_summary.txt`: same, human-readable.
- `steps/*.json`: full export of each Step, as returned by `export()`.
- `figures/*`: images produced by plotting steps.

---

### Extension Guide

**Add a Reader**

1. Create a new module in `src/reader/readers/`.
2. Subclass `Reader`.
3. Declare `extensions`, `requires_siblings`, `excludes_siblings`, `handles_compression`.
4. Implement `read(self, path, dims, labels, **args) -> Form`.
5. Use `unique_labels` to build labels.
6. For wide-table Readers only, use `get_encoder` for per-column encoding. Matrix Readers should not create encoders.
7. Fill `info` and `axis_info`.
8. Auto-discovered; no registration needed.

**Add a Step**

1. Create a new module in `src/task/step/steps/`.
2. Subclass `Step`.
3. Declare `name`, `inputs_arity`, `outputs`.
4. Implement `run(self, ctx, inputs) -> None`.
5. Optionally implement `export(self, ctx) -> dict`.
6. Output via `ctx[out_name] = Form(...)`.
7. Auto-discovered; no registration needed.

---

### Design Principles

- **Declarative orchestration**: `task.yaml` describes the pipeline.
- **Plugin Readers**: adding formats does not touch the core.
- **Plugin Steps**: adding operators does not touch the core.
- **Unified Form**: all data shares one model.
- **Complete label coverage**: every axis position must have a label.
- **Axis-parallel metadata sync**: `axis_info` guarantees subset safety.
- **Explicit errors**: a clear exception hierarchy.
- **Full export**: every step's result is traceable.
- **Classical backends**: `compare_groups`, `logrank_test`, `cox_regression`, and friends delegate to `scipy`, `statsmodels`, `lifelines`, and `pydeseq2`. The engine does not re-implement any statistical model.

---

### Engine Directory Structure

```text
scripts/
  run.py                    # entry point

src/
  core/
    errors/                 # error hierarchy
    forms/
      form.py               # Form data protocol

  reader/
    __init__.py             # read_source, pick_reader, auto-discovery
    base.py                 # Reader base class
    readers/                # format-specific Readers
      fasta_reader.py
      vcf_reader.py
      bed_reader.py
      csv_reader.py
      txt_reader.py
      h5ad_reader.py
      plink_reader.py
      bgen_reader.py
      mtx_reader.py
      ...

  task/
    __init__.py
    manifest.py             # task.yaml load and validation
    runner.py               # step scheduling
    context/
      base.py               # Context
    step/
      __init__.py           # Step auto-discovery
      base.py               # Step base class
      steps/                # operators
        describe.py
        transpose.py
        rename_dim.py
        select.py
        drop.py
        concat.py
        attach_info.py
        join.py
        aggregate.py
        filter_min.py
        filter_by.py
        missing.py
        maf.py
        hwe.py
        ld_prune.py
        normalize.py
        log_transform.py
        impute.py
        bin.py
        pca.py
        reduce.py
        reduce_axis.py
        rank_axis.py
        cluster_axis.py
        compare_groups.py
        regress.py
        correction.py
        diversity.py
        distance_matrix.py
        correlation.py
        permanova.py
        kaplan_meier.py
        logrank_test.py
        cox_regression.py
        forest_plot.py
        histogram.py
        scatter.py
        line.py
        manhattan.py
        volcano.py
        ma_plot.py
        heatmap.py
        boxplot.py
        violin.py
        dotplot.py
        barplot.py
        _plot_helpers.py

tasks/
  csv_demo/
  gwas_demo/
  rnaseq_de_demo/
  proteomics_de_demo/
  survival_demo/
  scrnaseq_demo/
  microbiome_demo/
  <operator>_demo/         # one per operator

docs/
  changelog/
    upstream/
      README.md
      v1.md
      v2.md

environment.yml             # Conda environment definition
requirements.txt            # pip dependency manifest
requirements-readers.txt    # optional format-specific readers
requirements-analysis.txt   # optional analysis dependencies
```

---

### Engine Development and Testing

```bash
# Activate the environment
conda activate biopipe

# Run the full test suite
pytest

# Run an example task
python scripts/run.py tasks/csv_demo

# Run any operator demo
python tasks/<operator>_demo/test_<operator>.py
python scripts/run.py tasks/<operator>_demo
```

An opt-in fixed-order resource planner supports lazy sources, run-local disk spill/reload, per-run logs, and streaming `describe`. Use `requirements-runtime.txt` for the portable CPU runtime; format-specific Readers require their optional dependencies.

---

### Engine License

Copyright (c) 2026 Haojian Li. All rights reserved.

This software is proprietary. No part of this software may be copied, modified, distributed, sublicensed, or used for commercial purposes without the prior written permission of the copyright holder.

For commercial licensing, custom development, or collaboration, please contact: email: lovegavin118@outlook.com / WeChat: mylovegavin118 / No. 13727316173.