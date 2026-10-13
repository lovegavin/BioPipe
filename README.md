# BioPipe

BioPipe is a local bioinformatics pipeline engine with a visual desktop workspace,
typed data contracts, bounded resource planning and an extensible operator SDK.
Create branched workflows, reuse saved routes as operators, and connect your own
AI agent through CLI or MCP. BioPipe itself does not supply an AI service.

Studio 0.3.0 preserves upstream Python Steps, Readers and YAML
tasks, with **46 built-in operators, 13 readers, six provider packages and five
reusable route templates**: GWAS, RNA-seq DE, Proteomics DE, survival analysis and
[16S microbiome](docs/microbiome.md). The desktop package includes this catalog and
the latest editor. Seven additional upstream axis/single-cell building blocks and
multi-group comparisons are also registered; their example YAML remains under `tasks/`.

Download the ready-built Windows desktop package from
[GitHub Releases](https://github.com/lovegavin/BioPipe/releases/latest).
Extract the complete ZIP, configure a Python environment as described in its
`START_HERE.txt`, then double-click `BioPipe Studio.exe`. Python and analysis
dependencies are not bundled. The repository contains development source;
compiled desktop distributions are release attachments.

See [release notes](docs/releases/v0.3.0.md) for this version and
[legacy/](legacy/README.md) for the archived previous source.

## Start Studio

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

Open `http://127.0.0.1:8765`. The generated CSV demo runs immediately. The input picker
accepts all registered reader formats, including PLINK and 10x MTX file sets;
uploading and saving do not require optional reader libraries. See
[input formats and file groups](docs/input_formats.md). Format-specific
dependencies are listed in `requirements-readers.txt`; DESeq2 and survival analyses
use `requirements-analysis.txt`. Dependencies can also be installed with uv.

On Windows, a built desktop distribution starts by double-clicking
`dist/BioPipe Studio/BioPipe Studio.exe`. The host bundles the frontend and backend
startup logic. Python, the backend source and analysis dependencies remain separate.
See [desktop setup](docs/desktop.md) and [portability](docs/portability.md).

Both desktop and development entry points use `~/.biopipe/studio` by default.
`BIOPIPE_STUDIO_HOME` or `--profile-dir` selects another shared profile;
`--workspace` explicitly isolates a workspace. CLI and MCP use the same resolver.
No developer username, installation drive or fixed backend port is embedded.

## Maintain built-in registries

```bash
python -m biopipe registry discover
python -m biopipe registry check
python -m biopipe registry build
# Optional, after git fetch origin main:
python -m biopipe registry discover --source-ref origin/main
```

The tool discovers new Step/Reader modules and route YAML, validates protocols and
DAG interfaces, and generates both JSON indexes. Routes come from `routes/**/task.yaml`
or `task.yml`; no route-name list is hardcoded in the generator. Invalid declarations
leave the existing indexes intact. See [registry maintenance](docs/registry_maintenance.md).

## Extend and automate

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

New plugins use the stable `biopipe_sdk` imports, JSON Schema parameters, explicit
info/axis contracts and standard Python entry points. Wheel installation updates
the JSON registry while Studio is open. Saved graphs and running jobs retain their
plugin version pins. Start with the [30-minute SDK tutorial](docs/sdk_quickstart.md).

Agents read semantic selection context and issue revision-checked edit batches.
Each batch is visible immediately and creates one undo entry. Execution is a
separate action; MCP requires `--allow-run` for it. The Agent panel also provides
copyable selection context and client revocation. See [CLI/MCP setup](docs/agent_api.md).

## Documentation

| Guide | Contents |
| --- | --- |
| [Registry maintenance](docs/registry_maintenance.md) | Discover additions, validate declarations, generate portable package/route indexes |
| [16S microbiome](docs/microbiome.md) | Abundance inputs, branches, new operators and resource behavior |
| [Operator protocol](docs/operator_protocol.md) | Descriptor, parameters, ports, outputs, versions and compatibility |
| [SDK quickstart](docs/sdk_quickstart.md) / [reference](docs/sdk_reference.md) | Operator and reader templates, testing and public Python APIs |
| [Plugin lifecycle](docs/plugins.md) | Hot installation, dependency isolation, pins and migration |
| [Agent interface](docs/agent_api.md) | CLI, MCP, context, atomic commands, permissions and events |
| [Data contracts](docs/data_contracts.md) | Static compatibility, runtime checks and metadata propagation |
| [Reusable routes](docs/route_operators.md) | Save/register separation, nested graphs and version snapshots |
| [Studio interaction](docs/frontend_requirements.md) | Canvas editing, panels, results and visual design |
| [Resource runtime](docs/resource_runtime.md) | Fixed budget, admission, spill, cache format and limits |
| [Desktop](docs/desktop.md) / [portability](docs/portability.md) | Build, launch, profiles and moving computers |

## Validation

```text
python -m pytest -q
cd frontend
npm test
npm run build
```

Install the `agent` and `dev` extras for the complete suite. Tests cover actual
plugin wheels/workers, reader dispatch, plugin upgrade/removal, route compatibility,
CLI processes, MCP stdio, revision conflicts, shared undo and data propagation.
Windows desktop verification is available in `scripts/verify_desktop.py`.

The resource budget is chosen once before a run. Actual sizes refine step admission;
emergency spill protects evictable data. It cannot preempt an active native allocation.
SDK plugins can implement the documented `flat-reduction-v1` stream or
`dense-writer-v1` Reader protocols. Built-in `describe` and H5AD/MTX retain those
capabilities. The new 16S kernels use full-memory execution with dedicated estimates;
CUDA kernels and arbitrary streaming transforms are not provided.

## Engine and upstream task reference

The following sections document the existing YAML engine and built-in implementation.
New external extensions should follow the SDK guides above.

A declarative, plugin-based bioinformatics pipeline framework.

BioPipe writes task workflows in `task.yaml`, reads external files into unified `Form` objects, and applies pluggable `Step` operators to filter, compute statistics, model, and plot those `Form` objects. The core goals are: **format and algorithm decoupling, label alignment safety, traceable outputs, validated extension registration**.

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
- [Full Example: GWAS Pipeline](#full-example-gwas-pipeline)
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
- **Plugin Readers**: add a protocol-compliant module and rebuild the index, or hot-install a Reader wheel.
- **Plugin Steps**: maintenance discovers new modules; protocol validation gates registration.
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

`environment.yml` declares a portable CPU environment for the engine and Studio. It has no machine-specific prefix, local build paths, or mandatory CUDA toolchain.

**Option 2: pip**

```bash
git clone https://github.com/lovegavin/BioPipe.git
cd BioPipe
pip install -r requirements.txt
```

`requirements.txt` installs the engine and Studio through portable package requirements. These are supported version ranges, not a platform-specific environment lock.

CSV, text annotation, FASTA and MTX support is included. Install `requirements-readers.txt` for the additional Parquet, AnnData, PLINK, BGEN and VCF readers, or install only the required reader's package. Native reader dependencies must be available for the target OS; they are loaded only when that format is used. The desktop launcher and core pipeline do not require CUDA.

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

`src/reader/__init__.py` loads explicit entry points from
`biopipe/builtin_packages.json`. The 13 readers ship as the `biopipe-readers`
package; a hot-installed replacement uses the same IDs and resource contracts.
Scanning is a maintenance command (`python scripts/build_builtin_packages.py --refresh`),
not a runtime registration mechanism.

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

Step is the operator layer. Filtering, selection, merging, transposition, PCA, regression, HWE, MAF, LD pruning, plotting — all are pluggable Steps.

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

`src/task/step/__init__.py` loads the checked-in package manifest into `STEPS`.
The 39 operators ship in core, genetics, expression, visualization and microbiome packages.
Package installation validates entry points and atomically publishes a new registry.
New workers load the selected package generation; running workers keep their lock.

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

| Category | Step |
|---|---|
| Data inspection | `describe` |
| Dimension/label | `transpose`, `rename_dim`, `select`, `drop`, `concat`, `attach_info` |
| QC filtering | `missing`, `maf`, `hwe`, `ld_prune` |
| Statistical modeling | `pca`, `regress`, `correction` |
| Plotting | `histogram`, `scatter`, `line`, `manhattan` |

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

## Output Structure

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

- `run_summary.json`: run index with step names, timings, inputs, parameters, export paths.
- `run_summary.txt`: human-readable index.
- `steps/*.json`: full export of each Step.
- `figures/*`: outputs of plotting steps.

---

## Extension Guide

For external plugins, use the [SDK quickstart](docs/sdk_quickstart.md) and
[protocol](docs/operator_protocol.md). The instructions below are for maintaining
built-ins inside the engine repository. Refresh the package index after source
changes, then build and hot-install the affected package to update an open Studio:

```bash
python scripts/build_builtin_packages.py --refresh
python scripts/build_builtin_packages.py --package biopipe-core --output build/packages
biopipe plugin install build/packages/biopipe-core/dist/biopipe_core-1.0.0-py3-none-any.whl
```

Bump the package version in the manifest for a published update. Direct edits to
the application's source still require a restart. See [unified packages and resource
protocols](docs/package_protocol.md) for disable/remove/restore, version locking,
streaming operators, disk readers and an executable SDK-only example.

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
8. Declare `parameters_schema` and `output_contract`; run `biopipe registry build` and review the generated index.

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
7. Declare `parameters_schema`, `input_contracts`, `output_contract` and any dynamic `output_parameter`; run `biopipe registry build`.

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
    __init__.py             # read_source, pick_reader, indexed providers
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
      __init__.py           # Indexed Step providers and maintenance scanning
      base.py               # Step base class
      steps/                # operators
        maf.py
        hwe.py
        pca.py
        regress.py
        correction.py
        manhattan.py
        scatter.py
        ...

tasks/
  csv_demo/                 # minimal CSV example
  gwas_demo/                # full GWAS pipeline example
  fasta_demo/               # FASTA example
  vcf_demo/                 # VCF example
  ...

environment.yml             # Conda environment definition
requirements.txt            # pip dependency manifest
```

---

## Development and Testing

An opt-in fixed-order resource planner now supports lazy sources, run-local
disk spill/reload, per-run logs, an RSS spill monitor, and streaming `describe`.
See [Resource runtime](docs/resource_runtime.md) for budgets, limitations and
reproducible verification. Use `requirements-runtime.txt` for the portable CPU
runtime; format-specific Readers require their optional dependencies.

```bash
# Activate the environment
conda activate biopipe

# Run tests
pytest

# Run an example task
python scripts/run.py tasks/csv_demo
```

---

## License

Copyright (c) 2026 Haojian Li. All rights reserved.

This software is proprietary. No part of this software may be copied, modified, distributed, sublicensed, or used for commercial purposes without the prior written permission of the copyright holder.

For commercial licensing, custom development, or collaboration, please contact: email: lovegavin118@outlook.com / WeChat: mylovegavin118 / No. 13727316173.

### Source preparation and Studio configuration

Managed H5AD and 10x MTX inputs now prepare dense disk arrays in bounded blocks,
then hand their actual size and retained clean blocks to the fixed-budget planner.
Large full-mode analysis still requires enough RAM; see [runtime details](docs/resource_runtime.md).
Studio preserves global YAML parameters and disabled memory settings, renames axis
label rules with dimensions, and supports configuration saves larger than 2 MiB.
Reader and plotting options are described in the registry and exposed in forms.
Use **Plugin management** in the operator library to install or remove local wheels;
see [plugin lifecycle](docs/plugins.md) and [input formats](docs/input_formats.md).
