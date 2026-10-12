# BioPipe

A declarative, plugin-based bioinformatics pipeline framework.

BioPipe writes task workflows in `task.yaml`, reads external files into unified `Form` objects, and applies pluggable `Step` operators to filter, compute statistics, model, and plot those `Form` objects. The core goals are: **format and algorithm decoupling, label alignment safety, traceable outputs, zero-registration extensibility**.

Repository: <https://github.com/lovegavin/BioPipe>

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
  - [Environment Setup](#environment-setup)
  - [Install Dependencies](#install-dependencies)
  - [Write task.yaml](#write-taskyaml)
  - [Run](#run)
  - [Output Overview](#output-overview)
- [Core Architecture: Four Protocols](#core-architecture-four-protocols)
  - [Protocol 1: Manifest Task Protocol](#protocol-1-manifest-task-protocol)
  - [Protocol 2: Reader Protocol](#protocol-2-reader-protocol)
  - [Protocol 3: Step Protocol](#protocol-3-step-protocol)
  - [Protocol 4: Form Data Protocol](#protocol-4-form-data-protocol)
- [Runtime: Context and Runner](#runtime-context-and-runner)
- [Built-in Readers](#built-in-readers)
- [Built-in Steps](#built-in-steps)
- [Operator Demos](#operator-demos)
- [Full Example: GWAS Pipeline](#full-example-gwas-pipeline)
- [Full Example: RNA-seq Differential Expression](#full-example-rna-seq-differential-expression)
- [Output Structure](#output-structure)
- [Extension Guide](#extension-guide)
  - [Add a Reader](#add-a-reader)
  - [Add a Step](#add-a-step)
- [Design Principles](#design-principles)
- [Directory Structure](#directory-structure)
- [Development and Testing](#development-and-testing)
- [License](#license)

---

## Features

- **Declarative orchestration**: describe "what to read, in what order to do what" in YAML.
- **Plugin Readers**: adding a new file format only requires a new module, no registry changes.
- **Plugin Steps**: adding a new operator only requires a new module, auto-discovered.
- **Unified Form model**: all data is an N-dimensional tensor with named dimensions, labels, and info.
- **Complete label coverage**: every axis position must have a label; filtering, merging and alignment never lose positions.
- **Axis-parallel metadata sync**: `axis_info` guarantees that arrays such as chromosome and position are trimmed together with axis subsets.
- **Full export**: every Step's complete result is written to `output/steps/`, with a run index in `run_summary.*`.
- **Explicit error hierarchy**: `BioPipeError` with `ReaderError`, `ManifestError`, `StepError`, `ValidationError`, `ContextError`.

---

## Quick Start

### Environment Setup

Python 3.11+ is required. Conda is recommended for environment management.

### Install Dependencies

**Option 1: Conda (recommended)**

```bash
git clone https://github.com/lovegavin/BioPipe.git
cd BioPipe
conda env create -f environment.yml
conda activate biopipe
```

`environment.yml` declares the full Conda environment, including Python 3.11, CUDA toolchain, and bioinformatics-specific packages such as `bed-reader`, `bgen-reader`, `cyvcf2`, `h5py`, `pgenlib`.

**Option 2: pip**

```bash
git clone https://github.com/lovegavin/BioPipe.git
cd BioPipe
pip install -r requirements.txt
```

`requirements.txt` pins exact versions of all Python dependencies, including `anndata`, `bed-reader`, `bgen-reader`, `cyvcf2`, `dask`, `h5py`, `statsmodels`, `matplotlib`, `scipy`, `pydeseq2`.

> **Note**: `environment.yml` and `requirements.txt` are **mandatory** dependency manifests, not optional. Missing any dependency causes the corresponding Reader or Step to raise `ReaderError` at runtime.

### Write task.yaml

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

This example comes from `tasks/csv_demo/task.yaml` in the repository. It demonstrates the three most basic things: declaring a source, specifying label rules, and invoking the `describe` Step.

### Run

```bash
python scripts/run.py tasks/csv_demo
```

### Output Overview

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

## Core Architecture: Four Protocols

BioPipe can be summarized as **four protocols/contracts**, plus two runtime components. The four protocols are the heart of the project; understanding them means understanding the whole framework.

| Protocol | Defined in | Question it answers | Key interface |
|---|---|---|---|
| **Manifest** | `task.yaml`, `src/task/manifest.py` | What to read? In what order to do what? | `sources`, `steps`, `labels`, `args`, `params` |
| **Reader** | `src/reader/base.py` | How does a file become a Form? | `extensions`, `requires_siblings`, `excludes_siblings`, `handles_compression`, `read()` |
| **Step** | `src/task/step/base.py` | How is a Form processed? | `name`, `inputs_arity`, `outputs`, `run()`, `export()` |
| **Form** | `src/core/forms/form.py` | What does the data look like? | `data`, `dims`, `labels`, `info`, `axis_info`, `validate()`, `subset_axis()` |

Runtime components:

- **Context**: holds `forms`, `params`, `step_params`, `metadata`, `artifacts`; manages output directories; writes `run_summary.*` at the end.
- **Runner**: executes steps in order, resolves inputs, checks outputs, writes per-step JSON.

In one sentence:
**Manifest orchestrates, Reader ingests, Step processes, Form unifies, Context/Runner runs.**

---

## Protocol 1: Manifest Task Protocol

The Manifest is the declarative orchestration layer. Users only write YAML, no Python.

### Top-level structure

```yaml
name: my_task
sources:
  ...
steps:
  ...
```

Optional top-level `params` is read by `Context` as task-level parameters.

### sources specification

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

### steps specification

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

### Execution flow

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

## Protocol 2: Reader Protocol

The Reader is the input adaptation layer, converting heterogeneous files such as FASTA, VCF, BED, CSV, H5AD, PLINK, BGEN into a unified `Form`.

### Base class contract

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

### Routing and auto-discovery

`src/reader/__init__.py` scans the `src.reader.readers` package:

- Imports each module.
- Finds `Reader` subclasses.
- Instantiates them and adds to `READERS`.
- New Readers only need a new module; no registry change.

`read_source(path, dims, labels, **args)` is the unified entry:

1. Calls `pick_reader(path)` to select the unique matching Reader.
2. If the Reader does not handle compression, decompresses to a temp file via `_decompressed`.
3. Calls `reader.read(...)`.

### Label rules

Label rules per dim support:

- `"builtin"`
- `"auto"`
- `{name: pos, ...}`
- When omitted, the specific Reader decides the default.

Duplicate labels are handled by `unique_labels`; the second occurrence gets `#<position>` appended.

### Encoding and info

- Non-numeric columns are encoded.
- Encoder instances are recorded in `info["encoders"]`.
- `info` typically contains `missing_code`, usually `np.nan`.
- Genotype Readers also write `ploidy`, `chrom`, `pos`, etc.
- If an info entry is parallel to an axis, it must be declared in `axis_info`.
- This allows `Form.subset_axis` to trim those arrays in sync.

---

## Protocol 3: Step Protocol

Step is the operator layer. Filtering, selection, merging, transposition, normalization, group comparison, PCA, regression, HWE, MAF, LD pruning, plotting — all are pluggable Steps.

### Base class contract

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

### Parameters and outputs

- Parameters are read from `ctx.step_params`.
- Runner injects `ctx.step_params["_input_names"]`.
- Steps register outputs via `ctx[out_name] = Form(...)`.
- `Context.__setitem__` automatically calls `form.validate()`.

### Auto-discovery

`src/task/step/__init__.py` scans `src.task.step.steps`:

- Imports modules.
- Finds `Step` subclasses.
- Requires `name != "unnamed"`.
- Builds `STEPS[name] = class`.
- Duplicate names raise an error.

### Error handling

- Input, parameter, and execution errors should raise `StepError`.
- Some Steps have explicit failure policies, e.g. `regress` only skips known non-fittable cases.

---

## Protocol 4: Form Data Protocol

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

### Constraints

- `len(dims) == data.ndim`.
- `dims` must not contain duplicates.
- Every dim must have labels.
- Every axis position must be covered by at least one label.
- Label positions must be int and within `0..size-1`.
- Each key listed in `axis_info[dim]` must exist in info and have length equal to the axis size.
- `subset_axis` trims data, labels, and axis-parallel info in sync.
- `get_parallel(field, dim)` retrieves a data column by label, or an info array by `axis_info`.

### Main methods

- `axis(name)`: returns the axis index.
- `get_parallel(field, dim)`: retrieves the parallel array.
- `subset_axis(dim, indices)`: subsets along a dim.
- `validate()`: structural validation.

---

## Runtime: Context and Runner

### Context

Location: `src/task/context/base.py`

Responsibilities:

- Holds `forms`, `params`, `step_params`, `metadata`, `artifacts`.
- Manages `out_dir`.
- `__setitem__` automatically calls `form.validate()`.
- `finalize()` writes:
  - `output/run_summary.json`
  - `output/run_summary.txt`

### Runner

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

## Built-in Readers

| Reader | Extensions | Main layout | Notes |
|---|---|---|---|
| FastaReader | `.fasta` `.fa` `.fna` `.faa` | sequence × position | Nucleotide/protein sequences, NaN-padded |
| H5adReader | `.h5ad` | obs × var | AnnData, supports layers |
| Gff3Reader | `.gff` `.gff3` | row × 9 columns | GFF3 annotation |
| GtfReader | `.gtf` | row × 9 columns | GTF annotation |
| VcfReader | `.vcf` `.vcf.gz` | variant × sample | GT to ALT count |
| BedReader | `.bed` | row × column | UCSC BED, 3–12 columns |
| CsvReader | `.csv` | row × column | Header supported |
| ParquetReader | `.parquet` | row × column | Column names from metadata |
| MtxReader | `.mtx` | gene × cell | 10x MEX |
| Plink1Reader | `.bed` + `.bim` + `.fam` | variant × sample | PLINK 1.x |
| Plink2Reader | `.pgen` + `.pvar` + `.psam` | variant × sample | PLINK 2.x |
| BgenReader | `.bgen` | variant × sample | Expected ALT dosage |

---

## Built-in Steps

Every Step is domain-agnostic: it operates on any `Form` whose dimensions match its parameters. Steps are grouped below by purpose. For each step, `In` is the number of inputs, `Out` is the context key (`params.output`), and the listed parameters are the ones the step reads from `ctx.step_params`.

### Data inspection

#### `describe`

Print and export a summary of one input form. No parameters.

- **In**: 1
- **Params**: none
- **Export**: shape, dims, info, labels, global stats (min/max/mean/std/n_valid/n_missing)

---

### Dimension and label

#### `transpose`

Reorder the axes of a form. Labels are unchanged; only axis order changes.

- **In**: 1
- **Params**:
  - `order` (list of dim names, required): the desired new axis order
  - `output` (default `transpose`)

#### `rename_dim`

Rename a single dimension.

- **In**: 1
- **Params**:
  - `from` (str, required): current dim name
  - `to` (str, required): new dim name
  - `output` (default `rename_dim`)

#### `select`

Keep only the listed labels along one dimension.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `labels` (list, required): label names to keep, in output order
  - `output` (default `select`)

#### `drop`

Remove named labels from one dimension.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `labels` (list, required): label names to remove
  - `output` (default `drop`)

#### `concat`

Concatenate several forms along one dimension. Aligns on non-axis dims by label intersection.

- **In**: `"*"` (at least 2)
- **Params**:
  - `axis` (str, required): dim to concatenate along
  - `align` (optional): `{dim: <name>, key: {input_name: label}}` for key-based alignment
  - `label` (optional): name for the merged key column
  - `output` (required)

#### `attach_info`

Attach axis-parallel info arrays from a source form onto a target, aligned by label.

- **In**: 2 (target, source)
- **Params**:
  - `fields` (list, required): info keys to attach
  - `target_dim` (str, required)
  - `output` (default `attach_info`)

---

### QC filtering

#### `filter_min`

Drop positions along `dim` whose value does not reach `min_value` in at least `min_samples` samples.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `min_value` (float, default 1)
  - `min_samples` (int, default 1)
  - `output` (default `filter_min`)
- **Export**: `kept_labels`, `dropped_labels`, counts

#### `missing`

Filter positions along one dimension by missing rate.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `threshold` (float, default 0.10): max allowed missing rate
  - `output` (default `missing`)

#### `maf`

Filter positions along one dimension by minor allele frequency.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `threshold` (float, default 0.01): minimum allowed MAF
  - `output` (default `maf`)
- **Requires**: `form.info["missing_code"]` and `form.info["ploidy"]`

#### `hwe`

Filter positions along one dimension by Hardy-Weinberg exact test p-value.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `threshold` (float, default 1e-6): minimum allowed p-value
  - `output` (default `hwe`)
- **Requires**: `form.info["missing_code"]` and `form.info["ploidy"] == 2`

#### `ld_prune`

Prune positions along one dimension by pairwise LD.

- **In**: 1
- **Params**:
  - `dim` (str, required)
  - `window` (int, default 50): window size in positions
  - `r2` (float, default 0.2): r² threshold
  - `output` (default `ld_prune`)

---

### Transformation

#### `normalize`

Scale a form along one dimension. Methods:

- `cpm`: counts per million, scaled to `target_sum`
- `total`: divide each sample by its total
- `median_of_ratios`: DESeq2-style size factors
- `zscore`: column-wise z-score

- **In**: 1
- **Params**:
  - `method` (str, required)
  - `dim` (str, required): typically the sample axis
  - `target_sum` (float, default 1e6, only for `cpm`)
  - `output` (default `normalize`)
- **Export**: per-sample `size_factor`, `sum_before`, `sum_after`, min/max/mean/std

#### `log_transform`

Apply `log_base(x + pseudocount)` elementwise. Missing values preserved.

- **In**: 1
- **Params**:
  - `base` (int, float, or `"e"`, default 2)
  - `pseudocount` (float, default 1, must be > 0)
  - `output` (default `log_transform`)
- **Export**: `before` and `after` distributions (min/max/mean/std/quartiles)

---

### Statistical modeling

#### `compare_groups`

Two-group comparison along one dimension. All statistics delegated to classical libraries:

- `ttest` → `scipy.stats.ttest_ind(equal_var=True)`
- `welch` → `scipy.stats.ttest_ind(equal_var=False)`
- `mannwhitney` → `scipy.stats.mannwhitneyu`
- `deseq2` → `pydeseq2` negative binomial GLM

- **In**: 2 (data form, metadata form)
- **Params**:
  - `dim` (str, required): feature dim of the data form
  - `group_dim` (str, required): sample dim shared by both forms
  - `group_label` (str, required): column on the metadata's other dim
  - `group_a` (str or int, required)
  - `group_b` (str or int, required)
  - `method` (str, default `ttest`)
  - `output` (default `compare_groups`)
- **Output form**: `dims = [dim, "statistic"]`; `statistic` labels are `log2FC`, `mean_a`, `mean_b`, `stat`, `P`, `N`, plus `Q_VALUE` when `method="deseq2"`
- **Export**: per-feature results and per-feature failures

#### `pca`

Principal component analysis along one dimension of a 2D form.

- **In**: 1
- **Params**:
  - `dim` (str, required): dim to compress
  - `n_components` (int, default 10)
  - `output` (default `pca`)
- **Requires**: `form.info["missing_code"]`
- **Output form**: `dims = [<observation dim>, "component"]`; labels are `PC1`, `PC2`, ...

#### `regress`

Multiple regression over one dimension of a wide form. Tests each remaining position as a predictor, adjusting for covariates.

- **In**: 1
- **Params**:
  - `dim` (str, required): dimension to iterate over
  - `response` (str, required): label of the response column
  - `covariates` (list, optional)
  - `method` (str, default `auto`): `ols`, `logit`, or `auto`
  - `output` (default `regress`)
- **Output form**: `dims = [dim, "statistic"]` with `BETA`, `SE`, `P`, `N`

#### `correction`

Multiple-testing correction on a result table. Adds `Q_VALUE` and `SIGNIFICANT` columns.

- **In**: 1
- **Params**:
  - `method` (str, required): `bonferroni` or `fdr`
  - `alpha` (float, default 0.05)
  - `pfield` (str, default `P`): name of the p-value column
  - `dim` (str, default `statistic`)
  - `output` (default `correction`)

---

### Plotting

All plotting steps write to `output/figures/<filename>` and do not modify the Context. They have `outputs = []`.

#### `volcano`

Volcano plot: x = log2FC, y = -log10(P), color by significance.

- **In**: 1
- **Params**:
  - `dim` (default `gene`)
  - `stat_dim` (default `statistic`)
  - `lfc_label` (default `log2FC`)
  - `p_label` (default `P`)
  - `lfc_threshold` (float, default 1.0)
  - `p_threshold` (float, default 0.05)
  - `filename` (required)
  - `title`, `xlabel`, `ylabel`, `point_size`, `alpha`, `label_top` (optional)

#### `ma_plot`

MA plot: x = log2 mean, y = log2FC, color by P < threshold.

- **In**: 1
- **Params**:
  - `dim` (default `gene`)
  - `stat_dim` (default `statistic`)
  - `lfc_label` (default `log2FC`)
  - `mean_a_label` (default `mean_a`)
  - `mean_b_label` (default `mean_b`)
  - `p_label` (default `P`)
  - `p_threshold` (float, default 0.05)
  - `filename` (required)
  - `title`, `xlabel`, `ylabel`, `point_size`, `alpha`, `label_top` (optional)

#### `heatmap`

Matrix heatmap with optional row selection, standardization, and clustering.

- **In**: 1
- **Params**:
  - `dim` (default `feature`)
  - `other_dim` (default `sample`)
  - `select` (str, default `variance`): `variance`, `label`, or `all`
  - `top_n` (int, default 50, only for `select=variance`)
  - `labels` (list, required for `select=label`)
  - `standardize` (str, default `none`): `row`, `col`, or `none`
  - `cluster_rows` (bool, default True)
  - `cluster_cols` (bool, default True)
  - `filename` (required)
  - `title`, `cmap`, `nan_color`, `figsize`, `show_row_labels`, `show_col_labels` (optional)

#### `boxplot`

Boxplot of one value column split by groups from a metadata form.

- **In**: 2 (data form, metadata form)
- **Params**:
  - `dim` (default `feature`)
  - `value_label` (str, required): column to plot
  - `group_dim` (str, required): sample dim shared by both forms
  - `group_label` (str, required): column on the metadata's other dim
  - `groups` (list, optional): subset and order of groups to show
  - `filename` (required)
  - `title`, `xlabel`, `ylabel`, `show_points`, `point_size`, `point_alpha` (optional)
- **Export**: per-group summary (n, min, q25, median, q75, max, mean, std)

#### `histogram`

Histogram of one labeled column.

- **In**: 1
- **Params**:
  - `dim` (default `feature`)
  - `value_label` (str, required)
  - `bins` (int, default 40)
  - `filename` (required)
  - `title`, `xlabel`, `ylabel`, `log_y` (optional)

#### `scatter`

Scatter plot of two labeled columns, optional color group.

- **In**: 1
- **Params**:
  - `dim` (default `feature`)
  - `x_label`, `y_label` (required)
  - `color_label` (optional)
  - `filename` (required)
  - `title`, `xlabel`, `ylabel`, `point_size`, `alpha` (optional)

#### `line`

Line plot of one labeled column against another. Sorted by x by default.

- **In**: 1
- **Params**:
  - `dim` (default `feature`)
  - `x_label`, `y_label` (required)
  - `filename` (required)
  - `title`, `xlabel`, `ylabel`, `sort` (optional)

#### `manhattan`

Genome-wide Manhattan plot: -log10(P) against cumulative genomic position, chromosomes in natural order.

- **In**: 1
- **Params**:
  - `dim` (default `feature`)
  - `chrom_label`, `pos_label`, `p_label` (required)
  - `p_dim` (default: same as `dim`)
  - `filename` (required)
  - `threshold`, `title`, `point_size`, `alpha` (optional)

---

## Operator Demos

Each operator has a dedicated demo task under `tasks/<operator>_demo/` that runs the operator against real data and produces a JSON export plus optional figures.

| Demo | Operator | Data |
|---|---|---|
| `csv_demo` | `describe` | small CSV |
| `filter_min_demo` | `filter_min` | airway counts |
| `normalize_demo` | `normalize` | airway counts |
| `log_transform_demo` | `log_transform` | airway counts |
| `compare_groups_demo` | `compare_groups` | airway counts + metadata |
| `volcano_demo` | `volcano` | airway DE result |
| `ma_plot_demo` | `ma_plot` | airway DE result |
| `heatmap_demo` | `heatmap` | airway counts |
| `boxplot_demo` | `boxplot` | airway counts + metadata |

Full pipelines:

| Task | Description |
|---|---|
| `gwas_demo` | Complete GWAS workflow |
| `rnaseq_de_demo` | Complete RNA-seq differential expression workflow |

---

## Full Example: GWAS Pipeline

The following example comes from `tasks/gwas_demo/task.yaml` in the repository, showing a complete GWAS analysis workflow:

```yaml
name: gwas_demo

sources:
  geno:
    path: input/geno.vcf
    dims: [variant, sample]
    labels:
      variant: builtin
      sample: builtin
  pheno:
    path: input/phenotype.csv
    dims: [sample, feature]
    labels:
      sample: {feature: 0}
      feature: builtin
  covar:
    path: input/covariates.csv
    dims: [sample, feature]
    labels:
      sample: {feature: 0}
      feature: builtin

steps:
  - name: missing
    inputs: [geno]
    params: {dim: sample, threshold: 0.10, output: geno_sm}
  - name: missing
    inputs: [geno_sm]
    params: {dim: variant, threshold: 0.05, output: geno_vm}
  - name: maf
    inputs: [geno_vm]
    params: {dim: variant, threshold: 0.05, output: geno_maf}
  - name: hwe
    inputs: [geno_maf]
    params: {dim: variant, threshold: 1.0e-4, output: geno_hwe}
  - name: ld_prune
    inputs: [geno_hwe]
    params: {dim: variant, window: 50, r2: 0.2, output: geno_pruned}
  - name: pca
    inputs: [geno_pruned]
    params: {dim: variant, n_components: 10, output: pcs}
  - name: transpose
    inputs: [geno_hwe]
    params: {order: [sample, variant], output: geno_T}
  - name: rename_dim
    inputs: [geno_T]
    params: {from: variant, to: feature, output: geno_f}
  - name: concat
    inputs: [geno_f, pheno, covar]
    params: {axis: feature, output: combined}
  - name: regress
    inputs: [combined]
    params:
      dim: feature
      response: trait_value
      covariates: [sex, batch]
      output: raw
  - name: correction
    inputs: [raw]
    params: {method: fdr, alpha: 0.05, output: assoc_result}
  - name: attach_info
    inputs: [assoc_result, geno_hwe]
    params:
      fields: [chrom, pos]
      target_dim: feature
      output: assoc_with_pos
  - name: manhattan
    inputs: [assoc_with_pos]
    params:
      dim: feature
      chrom_label: chrom
      pos_label: pos
      p_dim: statistic
      p_label: P
      filename: manhattan.png
      title: GWAS Manhattan plot
  - name: scatter
    inputs: [pcs]
    params:
      dim: component
      x_label: PC1
      y_label: PC2
      filename: pca_scatter.png
  - name: histogram
    inputs: [assoc_result]
    params:
      dim: statistic
      value_label: P
      bins: 20
      filename: pvalue_hist.png
  - name: describe
    inputs: [assoc_result]
```

Run:

```bash
python scripts/run.py tasks/gwas_demo
```

---

## Full Example: RNA-seq Differential Expression

The following example comes from `tasks/rnaseq_de_demo/task.yaml` in the repository, showing a complete RNA-seq differential expression workflow on the airway dataset (8 samples, 4 treated / 4 control).

```yaml
name: rnaseq_de_demo

sources:
  counts:
    path: input/airway_counts.csv
    dims: [gene, sample]
    labels:
      gene: {sample: 0}
      sample: builtin

  meta:
    path: input/airway_colData.csv
    dims: [sample, feature]
    labels:
      sample: {feature: 0}
      feature: builtin

steps:
  # 1. Filter low-expression genes
  - name: filter_min
    inputs: [counts]
    params:
      dim: gene
      min_value: 10
      min_samples: 3
      output: counts_filtered

  # 2. Differential expression: DESeq2 negative binomial GLM
  - name: compare_groups
    inputs: [counts_filtered, meta]
    params:
      dim: gene
      group_dim: sample
      group_label: dex
      group_a: untrt
      group_b: trt
      method: deseq2
      output: de_result

  # 3. Visualization: volcano and MA plot
  - name: volcano
    inputs: [de_result]
    params:
      dim: gene
      stat_dim: statistic
      lfc_label: log2FC
      p_label: Q_VALUE
      lfc_threshold: 1.0
      p_threshold: 0.05
      filename: volcano.png
      title: "Airway: dex vs untrt"
      label_top: 8

  - name: ma_plot
    inputs: [de_result]
    params:
      dim: gene
      stat_dim: statistic
      lfc_label: log2FC
      mean_a_label: mean_a
      mean_b_label: mean_b
      p_label: Q_VALUE
      p_threshold: 0.05
      filename: ma.png
      title: "Airway: dex vs untrt"

  # 4. Normalization and log transform for exploratory visualization
  - name: normalize
    inputs: [counts_filtered]
    params:
      method: cpm
      dim: sample
      target_sum: 1e6
      output: counts_cpm

  - name: log_transform
    inputs: [counts_cpm]
    params:
      base: 2
      pseudocount: 1
      output: counts_log

  # 5. Sample clustering check: PCA + scatter
  - name: pca
    inputs: [counts_log]
    params:
      dim: gene
      n_components: 10
      output: pcs

  - name: scatter
    inputs: [pcs]
    params:
      dim: component
      x_label: PC1
      y_label: PC2
      filename: pca.png
      title: "Sample PCA"

  # 6. Heatmap of the top 50 most variable genes
  - name: heatmap
    inputs: [counts_log]
    params:
      dim: gene
      other_dim: sample
      select: variance
      top_n: 50
      standardize: row
      cluster_rows: true
      cluster_cols: true
      filename: top50_heatmap.png
      title: "Top 50 variable genes"

  # 7. Single-gene boxplot: ZBTB16 (a canonical dex-induced marker)
  - name: transpose
    inputs: [counts_log]
    params:
      order: [sample, gene]
      output: samples_by_gene

  - name: boxplot
    inputs: [samples_by_gene, meta]
    params:
      dim: gene
      value_label: ENSG00000109906
      group_dim: sample
      group_label: dex
      filename: ZBTB16_boxplot.png
      title: "ZBTB16 by dex"
      ylabel: "log2(CPM + 1)"

  # 8. Result summary
  - name: describe
    inputs: [de_result]
```

Download the data (airway, GSE52778):

```bash
mkdir -p tasks/rnaseq_de_demo/input
cd tasks/rnaseq_de_demo/input

wget -O airway_counts.csv \
  "http://ftp.dk.xemacs.org/bioconductor/help/course-materials/2022/CSAMA/lecture/1-monday/lecture-01-data/airway_counts.csv"

wget -O airway_colData.csv \
  "http://ftp.dk.xemacs.org/bioconductor/help/course-materials/2022/CSAMA/lecture/1-monday/lecture-01-data/airway_colData.csv"
```

Run:

```bash
python scripts/run.py tasks/rnaseq_de_demo
```

---

## Output Structure

Example output for the GWAS pipeline:

```text
output/
  run_summary.json
  run_summary.txt
  steps/
    01_missing.json
    02_missing.json
    03_maf.json
    04_hwe.json
    05_ld_prune.json
    06_pca.json
    07_transpose.json
    08_rename_dim.json
    09_concat.json
    10_regress.json
    11_correction.json
    12_attach_info.json
    13_manhattan.json
    14_scatter.json
    15_histogram.json
    16_describe.json
  figures/
    manhattan.png
    pca_scatter.png
    pvalue_hist.png
```

Example output for the RNA-seq DE pipeline:

```text
output/
  run_summary.json
  run_summary.txt
  steps/
    01_filter_min.json
    02_compare_groups.json
    03_volcano.json
    04_ma_plot.json
    05_normalize.json
    06_log_transform.json
    07_pca.json
    08_scatter.json
    09_heatmap.json
    10_transpose.json
    11_boxplot.json
    12_describe.json
  figures/
    volcano.png
    ma.png
    pca.png
    top50_heatmap.png
    ZBTB16_boxplot.png
```

- `run_summary.json`: run index with step names, timings, inputs, parameters, export paths.
- `run_summary.txt`: human-readable index.
- `steps/*.json`: full export of each Step.
- `figures/*`: outputs of plotting steps.

---

## Extension Guide

### Add a Reader

1. Create a new module in `src/reader/readers/`.
2. Subclass `Reader`.
3. Declare:
   - `extensions`
   - `requires_siblings`
   - `excludes_siblings`
   - `handles_compression`
4. Implement:
   ```python
   def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
       ...
   ```
5. Use `unique_labels` to handle labels.
6. Use `get_encoder` for encoding when necessary.
7. Fill `info` and `axis_info`.
8. Auto-discovered; no registration needed.

### Add a Step

1. Create a new module in `src/task/step/steps/`.
2. Subclass `Step`.
3. Declare:
   - `name`
   - `inputs_arity`
   - `outputs`
4. Implement:
   ```python
   def run(self, ctx: Context, inputs: list[Form]) -> None:
       ...
   ```
5. Optionally implement:
   ```python
   def export(self, ctx: Context) -> dict:
       ...
   ```
6. Output via `ctx[out_name] = Form(...)`.
7. Auto-discovered; no registration needed.

---

## Design Principles

- **Declarative orchestration**: task.yaml describes the pipeline.
- **Plugin Readers**: adding formats does not touch the core.
- **Plugin Steps**: adding operators does not touch the core.
- **Unified Form**: all data shares one model.
- **Complete label coverage**: every axis position must have a label.
- **Axis-parallel metadata sync**: `axis_info` guarantees subset safety.
- **Explicit errors**: a clear exception hierarchy.
- **Full export**: every step's result is traceable.
- **Classical backends**: `compare_groups` delegates all statistics to `scipy` and `pydeseq2`; no statistical model is re-implemented.

---

## Directory Structure

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
        # data inspection
        describe.py
        # dimension / label
        transpose.py
        rename_dim.py
        select.py
        drop.py
        concat.py
        attach_info.py
        # QC filtering
        filter_min.py
        missing.py
        maf.py
        hwe.py
        ld_prune.py
        # transformation
        normalize.py
        log_transform.py
        # statistical modeling
        compare_groups.py
        pca.py
        regress.py
        correction.py
        # plotting
        volcano.py
        ma_plot.py
        heatmap.py
        boxplot.py
        histogram.py
        scatter.py
        line.py
        manhattan.py
        _plot_helpers.py

tasks/
  csv_demo/                 # minimal CSV example
  gwas_demo/                # full GWAS pipeline example
  rnaseq_de_demo/           # full RNA-seq DE pipeline example
  fasta_demo/               # FASTA example
  vcf_demo/                 # VCF example
  filter_min_demo/          # operator demo: filter_min
  normalize_demo/           # operator demo: normalize
  log_transform_demo/       # operator demo: log_transform
  compare_groups_demo/      # operator demo: compare_groups
  volcano_demo/             # operator demo: volcano
  ma_plot_demo/             # operator demo: ma_plot
  heatmap_demo/             # operator demo: heatmap
  boxplot_demo/             # operator demo: boxplot
  ...

environment.yml             # Conda environment definition
requirements.txt            # pip dependency manifest
```

---

## Development and Testing

```bash
# Activate the environment
conda activate biopipe

# Run the full test suite
pytest

# Run an example task
python scripts/run.py tasks/csv_demo

# Run an operator demo
python scripts/run.py tasks/filter_min_demo
python scripts/run.py tasks/compare_groups_demo

# Run the end-to-end RNA-seq DE pipeline
python scripts/run.py tasks/rnaseq_de_demo
```

---

## License

Copyright (c) 2026 Haojian Li. All rights reserved.

This software is proprietary. No part of this software may be copied, modified, distributed, sublicensed, or used for commercial purposes without the prior written permission of the copyright holder.

For commercial licensing, custom development, or collaboration, please contact: email: lovegavin118@outlook.com / WeChat: mylovegavin118 / No. 13727316173.