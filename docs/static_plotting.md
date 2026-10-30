# Static plotting adapters (protocol v3)

BioPipe keeps the existing operator protocol: Python implementation, separate
parameter-schema JSON, and frozen per-workflow/per-run parameter values. Plotting
backends are implementation choices. Neither Matplotlib Figure objects nor R
objects cross worker boundaries. Files and JSON reports do.

## Public figure SDK

```python
from biopipe_sdk import publication_style, save_matplotlib, figure_collection
publication_style(context)
# fig_a and fig_b are author-created Matplotlib figures.
report = figure_collection(
    save_matplotlib(context, fig_a, "volcano.pdf", figure_id="volcano", title="Volcano"),
    save_matplotlib(context, fig_b, "heatmap.pdf", figure_id="heatmap", title="Heatmap"),
)
return report
```

`save_matplotlib` writes PNG/PDF/SVG, preserves requested supported formats,
uses physical size/DPI parameters, avoids overwriting existing files and closes
the figure. `publication_style` explicitly applies the static publication theme;
it does not inherit Studio's theme. Different panels can be composed by the
underlying library before saving. Domain tools retain their native capabilities.

For R, command-line tools, or another renderer, save files first, then describe them:

```python
from biopipe_sdk import register_figure
return register_figure(context, "heatmap", {
    "pdf": output_dir / "heatmap.pdf",
    "svg": output_dir / "heatmap.svg",
    "png": output_dir / "heatmap.png",
}, title="Expression heatmap", width_mm=120, height_mm=90, dpi=300)
```

Files must exist below `context.out_dir`; use `context.artifact_path` to allocate
paths. Registration validates containment and matching extensions without loading
image pixels. IDs are portable identifiers, unique per logical figure within a
step. Every format of that figure shares its ID. `figure_collection` rejects
repeated `(id, format)` pairs. Optional metadata: title, description, positive
finite width_mm, height_mm, dpi. An operator returns JSON like:

```json
{"figures": [
  {"id":"volcano","title":"Volcano","format":"pdf","path":"<job>/output/artifacts/volcano.pdf","filename":"volcano.pdf"},
  {"id":"heatmap","title":"Heatmap","format":"pdf","path":"<job>/output/artifacts/heatmap.pdf","filename":"heatmap.pdf"}
]}
```

Studio lists each figure separately, lazily previews raster/SVG representations,
and directly opens the saved original. The endpoint selects
`/api/jobs/<job>/exports/<step>/figure?figure_id=heatmap&format=pdf`.
Local, coordinated and SSH jobs forward the same ID; remote download caches include
it. Originals are fetched when opened, not regenerated. Existing single-figure
reports with `path`, `figure_path` or ID-less `figures` remain readable.

## Optional R dependency declaration

Keep Python packages in `dependencies`. Declare R in the existing `resources`
object; no new protocol version or top-level operator type is required:

```json
{"resources": {
  "memory_modes": ["full"],
  "estimate": "estimate_memory",
  "r": {
    "version": ">=4.3,<5",
    "packages": [
      {"name":"ggplot2", "source":"cran", "version":">=3.5"},
      {"name":"ComplexHeatmap", "source":"bioconductor", "version":">=2.18"}
    ]
  }
}}
```

Names, sources and version constraints are validated without executing operator
code. `source` is `cran` or `bioconductor`. Optionally specify a Bioconductor
release, for example `"bioconductor":"3.20"`, together with a compatible R
constraint. Unsupported/inconsistent combinations fail with the install/probe
error; BioPipe never silently weakens a constraint. CRAN exact `==` constraints
use `remotes::install_version`; other constraints install the repository candidate
and verify it. Bioconductor uses `BiocManager::install(ask=FALSE, update=FALSE)`;
choose a release compatible with required package versions. This is not a promise
that arbitrary historical/native packages can install on every operating system.

The dependency service retains `unchecked / checking / installing / passed /
failed` states. Passed entries are not rechecked during the same session. New or
changed R requirements invalidate that operator's fingerprint; failures remain
retryable. Python dependency checks and isolation continue unchanged. R declaration
changes also invalidate server readiness. Server registry refresh prepares missing
R dependencies without changing its existing Python inspection policy. Source
discovery remains metadata-only.

On repair, BioPipe uses a compatible `Rscript` on PATH, or bootstraps a user-local
R through micromamba/conda-forge (Windows x64, Linux x64/aarch64, macOS x64/arm64).
CRAN packages come from cloud.r-project.org; Bioconductor installs use BiocManager.
There is no administrator or shell-profile requirement. Installation needs network
access, free disk space and compatible repository packages. Native source packages
may require system build libraries; failure is reported rather than treated as ready.

Libraries are isolated by normalized R requirements. A repair builds a new library,
checks actual R/package versions and loads namespaces, then atomically publishes a
receipt. It never updates an existing job's package library or the user's R library.
Receipts record resolved versions; they are not a complete transitive cross-machine
lockfile. Prefer exact constraints and an explicit Bioconductor release when needed.

The default directory follows the selected Studio profile:
`<data-dir>/runtimes/r`. Workers inherit the plugin installation's runtime root;
servers use their own profile, never a desktop path. Standalone scripts can set
`BIOPIPE_R_HOME` to a writable runtime directory, and `BIOPIPE_RSCRIPT` to an explicit
compatible interpreter. These are user overrides, not paths embedded in packages.
Managed receipts are reusable across launches; session checks can verify them again.
The SDK also prepares missing R dependencies before executing an R adapter.

## Run R with frozen parameters

```python
from biopipe_sdk import run_r
output_dir = run_r(context, self.definition["resources"]["r"], R_SCRIPT,
                   inputs={"matrix": str(matrix_path)})
```

`R_SCRIPT` is source text in the Python implementation, covered by its existing v3
code hash. Do not hide executable R code in a mutable parameter JSON. The runner
writes a separate request JSON containing the actual `context.step_params`, file
references and a unique output directory. In R, `params`, `inputs` and `output_dir`
are provided automatically (`jsonlite` is a managed runtime dependency). Parameter
values are never interpolated into executable R code. R version records and output
are logged; failures propagate to the normal job log. Keep large datasets in files,
not JSON. The SDK does not implement a general in-memory Python-to-R object bridge.

## Memory and scientific responsibility

The existing planner, disk-backed readers, IPC and emergency spilling remain in
place. R runs as a child process, included in existing process-tree accounting and
job cancellation. This does **not** make R's heap spillable by Python: declare a
realistic temporary-memory estimate. Clustering can require quadratic workspace.
Use upstream row/region selection or a backend with genuine bounded processing.
Do not declare `stream` simply because data was written to a TSV in chunks.

The examples declare `full` and explicit estimates. ComplexHeatmap writes selected
rows sequentially to a disk exchange file, then R loads that selected matrix.
`top_n=0` means all rows and can be expensive. Saved dimensions, DPI, fonts, display
selection and scientific thresholds stay in each route's own parameter values.
PDF/SVG may contain rasterized dense artists; they are not necessarily all-vector.

## Examples and verification

See [the installable examples](../examples/plotting_plugin/README.md): a Python
volcano plot plus companion distribution, and an R ComplexHeatmap adapter. Both
use v3 declarations and their own `*.parameters.json`. The examples are optional,
so installing BioPipe alone does not download R or large domain packages.

References: [R library installation](https://stat.ethz.ch/CRAN/doc/manuals/r-devel/R-admin.html),
[BiocManager installation](https://bioconductor.github.io/BiocManager/reference/install.html),
[micromamba](https://mamba.readthedocs.io/en/stable/installation/micromamba-installation.html).
