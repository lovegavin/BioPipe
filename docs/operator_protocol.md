# BioPipe Operator Protocol v2

Status: protocol v2, SDK 2.0.0, in the next development version. Python 3.11 or newer is required.
This is the single public declaration contract for all 64 built-in Steps, 15 Readers
and external extensions. Existing IDs and calculation semantics are retained.
Protocol v1 declarations and graph v1 files require [explicit migration](migration_v2.md);
the live runtime does not load their compatibility adapters.

Reader descriptors may also provide optional `file_input` metadata for Studio's
file picker, default dimensions/labels and companion-file checks. See the
[input metadata contract](input_formats.md#reader-extension-metadata). Existing
descriptors without this additive field remain valid.

## Identity and discovery

Studio's **Refresh library** scans normal Python modules in its operator/Reader
directories and registers their declarations without requiring authors to build a
package. The same descriptors and validation apply to source modules and installed
wheels. See [whole-library refresh](plugins.md#drop-refresh-use). A library source
module can retain the original built-in naming style; existing package ownership
cannot be reassigned by an update.

A distribution exposes classes through standard Python entry points:

```toml
[project.entry-points."biopipe.operators"]
scale = "my_lab:Scale"

[project.entry-points."biopipe.readers"]
matrix = "my_lab:ArrayReader"
```

The class `name` is the stable registry ID, such as `my_lab.scale`. New plugin IDs
must contain a namespace separator (`.`), match `[A-Za-z_][A-Za-z0-9_.-]{0,79}`,
and be unique across readers and operators. A replacement for a bundled package
may retain that package's existing IDs; unrelated packages cannot claim them.
The entry-point key is not the operator ID. `version` uses three numeric components
with an optional prerelease or build suffix. The distribution version identifies
the installed wheel; an individual operator version describes its interface.

`biopipe plugin build` generates `biopipe-plugin.json` and embeds the same descriptor
in the wheel's `.dist-info/biopipe.json`, with an updated wheel RECORD. Installation
checks the descriptor against the implementation in a separate probe process.
Ordinary wheels built by other Python tools may omit this generated file; their
entry points are probed once during installation. The GUI reads JSON metadata and
never imports plugin Python. Bundled entry points come from a checked-in package
manifest; scanning is only used to maintain that manifest.

## Descriptor envelope

Every reader and operator has these fields:

| Field | Meaning |
| --- | --- |
| `protocol_version` | Exactly `2` |
| `id`, `version`, `kind` | Stable identity; kind is `operator` or `reader` |
| `entry_point` | Python `module:Class` |
| `title`, `description` | Display text |
| `category`, `icon` | Optional library category and module-relative image path or Studio icon name; see below |
| `parameters_schema` | Self-contained JSON Schema 2020-12 object schema |
| `contracts` | Version 1 input and output data contracts |
| `resources` | Supported memory modes, CUDA declaration, estimation hook |
| `dependencies` | Optional PEP 508 requirement strings, such as `numpy>=1.26` |
| `dependency_imports` | Optional Python module names to verify in an isolated process |
| `implementation` (registry only) | Installed package name, version and content SHA-256; not part of an author descriptor |

Operators additionally expose `inputs_arity`, `outputs`, and `output_parameter`.
Readers expose `extensions`, `requires_siblings`, `excludes_siblings`, and
`handles_compression`, plus optional `file_input`. The canonical descriptor has
one identity (`id`), one parameter schema, one `contracts` object and one `resources`
object. The HTTP catalog adds derived `parameters` and `runtime_defaults` for
forms; these projections must not be written into provider manifests. There are no
`name`/`module` aliases, top-level `memory_modes`/`supports_cuda`, `input_type`/`output_type`
or Reader `output_contract` duplicates. Class attributes remain the authoring API.
Generated parameter forms support primitive fields, enums and JSON object/array
fields. Complex schema constraints are always checked by Python even when a custom
widget is unavailable.

Export machine-readable schemas with:

```text
biopipe schema operator
biopipe schema graph
biopipe schema workspace
```

Checked-in copies are in `biopipe_sdk/schemas/`. The descriptor envelope rejects unknown fields; semantic validation also checks arity, parameter schemas and contracts.

## Dependency declarations

Readers and Steps use the same optional class declarations:

```python
dependencies = ["scikit-learn>=1.5"]
dependency_imports = ["sklearn"]
```

Use distribution names in `dependencies` and importable module names in
`dependency_imports`; these names can differ. Versions, extras and environment
markers follow PEP 508. URLs, machine paths and pip flags are rejected. Keep
source declarations literal lists so Refresh can read them before importing
the module. Declare package-wide requirements in wheel `project.dependencies`; these are
merged into every installed entry. Keep conflicting per-operator requirements on
the individual classes and in the SDK manifest, not in the common package list.
If a declaration is omitted, BioPipe
cannot infer undeclared dependencies from arbitrary Python code.

Studio checks enabled entries at startup and after library changes. A passing
result stays valid for that implementation for the current session; retries only
visit unchecked or failed entries. Installation prepares a candidate generation
and preserves existing dependency versions. Failed resolution or native imports
leave the previous generation active. Version conflicts select private dependency
directories and subprocesses using the same Python; compatible entries stay shared.
See [selective isolation](dependency_isolation.md) and [dependency states](installation.md#dependency-state).

## Operator categories and icons

`kind` is the execution type. The SDK sets it to `operator` for `Step`/`Operator`
subclasses and `reader` for `Reader` subclasses. Use `category` for the operator's
purpose in the library. Package `origin` (`bundled` or `wheel`) describes how code
was installed; installing a plugin does not force it into a separate category.

Declare display metadata directly on the operator class:

```python
class EnrichGoStep(Step):
    name = "my_lab.enrich_go"
    category = "analysis"
    icon = "icons/enrichment.svg"  # Optional; relative to this Python file.
    # Declare parameter schema, contracts and run() as usual.
```

Recommended category keys are:

| Key | Library group | Default icon |
| --- | --- | --- |
| `quality_control` | Quality control | CheckSquare |
| `analysis` | Statistical analysis | Sigma |
| `data` | Data preparation | SlidersHorizontal |
| `visualization` | Visualization | ChartBar |
| `microbiome` | Microbiome | CirclesThree |

Custom category strings are also supported. Studio localizes common aliases so
equivalent English and Chinese categories appear in one group. Omitted or empty
categories appear under **Uncategorized**. Older `Plugins`/`Extensions` defaults
also appear there; their operator kind and package ownership remain unchanged.
Bundled operators declare their presentation on the implementation class as well.

`icon` optionally names an image relative to the Python module defining the class:

```text
steps/
  enrichment.py         # icon = "icons/enrichment.svg"
  icons/
    enrichment.svg
```

PNG, JPEG (`.jpg`/`.jpeg`), WebP, GIF and static SVG are supported. Images keep their
original colors and aspect ratio in the library, canvas and inspector. Use a square
asset with transparency where possible. A supplied image takes priority over the
existing chart glyph. SVG supports basic shapes, text, gradients, clipping and local
references; scripts, embedded HTML, external resources, DTDs and stylesheets are
rejected. Use presentation attributes or ordinary inline styles. Absolute paths,
parent traversal and remote URLs are not accepted.

Discovery validates and embeds the image in the generated `icon_image` data URI.
Authors only set `icon`; do not write `icon_image` manually. The registry contains
the actual bytes, so rendering is offline and independent of the author's source
location. Immutable generations retain their original image. Source-library refresh
also detects image-only edits. A missing or invalid declared asset fails validation
without replacing the previous registry; a browser image decoding failure uses the
category default.

For SDK wheels, include assets in package data, for example:

```toml
[tool.setuptools.package-data]
"my_lab" = ["icons/*.svg", "icons/*.png"]
```

`biopipe plugin build` checks that the wheel includes the exact declared images.
Normal operator-directory refresh copies image resources automatically. For a
single-file inbox drop-in, use a literal path such as `icon = "icons/enrichment.svg"`
and copy the `icons/` or `assets/` directory alongside the file. Those resource
directories are not treated as separate plugin projects.

Existing case-sensitive Phosphor names, such as `icon = "Intersect"`, remain
supported. Missing, empty, null or unknown names use the category default above;
unknown/custom categories use `SquaresFour`. Supported names are:

```text
ArrowsDownUp ArrowsIn ChartBar ChartLine ChartScatter CheckSquare
CirclesThree Columns Database Dna Funnel Function Intersect ListBullets
MinusSquare PuzzlePiece Ruler Scales Selection Shuffle Sigma
SlidersHorizontal SortAscending SquaresFour Stack Tag TextT
TreeStructure TrendUp Unite
```

Category and icon are optional typed fields in the public operator/package JSON
schemas. Both source registry maintenance and wheel builds copy declarations into
their descriptors. The implementation class is the sole source. Omitting an icon selects the category
default; visualization previews are explicit optional declarations.

For a source module or image edit, click **Refresh operator library** or run
`biopipe plugin refresh`; no application restart is needed. Maintainers additionally
run `biopipe registry build` and `biopipe registry check` before publishing the
repository's bundled index. For a wheel, rebuild and hot-install it. Refresh scans
the source directories shown by the running instance and publishes to its selected
profile; it does not edit the repository's checked-in manifests.
See [registry maintenance](registry_maintenance.md) and [plugin lifecycle](plugins.md).

## Parameters

Every Step and Reader must declare `parameters_schema`, including readers with no options.
The root must be an object. Use `additionalProperties: false` to catch misspellings.
Top-level property defaults are copied before validation. Nested defaults are not
materialized automatically. `$ref` and `$dynamicRef` may reference only local
fragments; validation never downloads remote schemas. Optional UI hints include
`title`, `enum`, `minimum`, `maximum`, `x-ui-step` and `x-ui-default`.
`default` is the execution default; `x-ui-default` is only a new-card preset.
For example, PCA retains execution default 10 and new-card preset 2. The registry
never reads method source code to infer defaults. `ui_defaults` on a class is an
optional map applied to these schema annotations when a shared schema is used.

Engine fields `output` and `_input_names` are not plugin calculation parameters.
The dynamic output parameter is named `output`. All calculation parameters are
validated on every execution. A built-in schema may explicitly allow additional
properties for its existing algorithm options; this is not a validation bypass.

## Data and port contracts

`Form` contains a numeric NumPy tensor `data`, ordered dimension names `dims`,
`labels[dimension][name] -> integer position`, global/array metadata `info`, and
`axis_info[dimension] -> list of info field names`. An array in `info` is associated
with an axis only when explicitly declared in `axis_info`.

`Form.validate()` checks shape, dimensions, unique label positions, axis annotation
lengths and encoder references. Input objects are shared between branches: treat
them and their nested metadata as immutable. Return a new Form and use SDK metadata
helpers when selecting, renaming or reducing axes. Do not infer biological semantics
from matrix shape or an annotation's length.

```python
from biopipe_sdk import MISSING, param, port

input_contracts = [port(
    ndim=2,
    dims=[param("dim")],
    info={"missing_code": MISSING,
          "representation": {"type": "string", "const": "hard_call"},
          "ploidy": {"type": "integer", "const": 2}},
    values="hard_call",
)]
output_contract = {"mode": "subset"}
```

Port contracts are a small BioPipe protocol, **not JSON Schema**. They support
`numeric`, `ndim`, required dimension names, info rules (`type`, `optional`, `const`,
`enum`, `min`, array `items`), required labels and parallel axis annotations.
`param(name, default)` resolves a requirement against current parameters.
`MISSING` accepts a numeric missing marker or null. Reader contracts use
`reader_contract()`; coordinate fields can be bound to the first declared axis.

An operator declares one input contract per port. `inputs_arity` is an integer
from 0 to 20, or `"*"` with one repeated contract. Variadic instances retain their
explicit canvas `input_count`; edge `targetHandle` determines input order.

Output inference supports the following common rules:

| Mode | Promise |
| --- | --- |
| `passthrough` | Preserve the first input's data schema |
| `subset`, `select`, `drop` | Preserve semantics while filtering labels/annotations |
| `transform` | Preserve axes, clear invalid genotype semantics, declare `representation` |
| `project` | Keep/drop axes, prepend/append declared axes, optionally clear obsolete semantics with `derived` |
| `choose` | Select an output rule by a parameter, with an optional fallback |
| `declare` | Supply a complete inferred schema under `schema`; parameters may be referenced |
| `rename`, `transpose`, `concat`, `attach` | Use the corresponding established metadata operation |
| `unknown` | No static guarantee beyond runtime Form validation |
| `report`, `none` | No Form output; registering one is an error |

`declare.schema` uses inferred-schema maps (`labels: {dim: [names]}`,
`axis_info: {dim: [fields]}`, `info: {field: rule}`), not the input port's lists.
The `info` map on an output rule can add guarantees, including a new representation. A custom algorithm must
actually perform the declared transformation; a descriptor does not transform data.

The contract supports data-independent axis composition. For example, a pairwise matrix:

```python
output_contract = {
    "mode": "project", "keep_dims": [param("dim")], "derived": True,
    "append_dims": [{"name": {"param": "dim", "suffix": "_b"},
                     "labels_from": param("dim")}],
    "info": {"missing_code": MISSING,
             "representation": {"type": "string", "const": "distance"}},
}
```

`drop_dims` removes axes from the kept set. Added dimensions use `name` and optional
`labels` (a list, parameter reference, or unknown/null), `labels_from` (a kept axis),
or `input_axis: [input_index, axis_index]` for a name obtained from another input.
Copied labels do not duplicate axis annotations onto a new axis. `labels_unknown`
discards label guarantees, and `axis_info_unknown` discards annotation guarantees
when membership changes in a way the analyzer cannot know. Unknown remains unknown;
no input matrix is read or synthetic fact asserted during inference.

A method-dependent rule uses `{"mode": "choose", "param": "method", "default":
"pca", "cases": {"pcoa": <rule>}, "otherwise": <rule>}`. Each branch is validated
recursively. Parameter references may specify a string `suffix`, as above. These
rules belong to data contract version 1, independent of descriptor version 2.

The backend analyzer reports `compatible`, `incompatible`, or `unknown` without
loading the full input. Known incompatibilities block wiring/compilation. Unknown
facts are checked after reading. Reader output, operator input and operator output
are validated at execution boundaries, before a new output enters the cache.

## Execution and resource estimates

For a single-output operator, subclass `Operator` and implement
`compute(inputs, params, context) -> Form`. For reports, set
`output_parameter = None`, use `output_contract = {"mode": "report"}`, and return
a JSON-compatible report. Advanced fixed multi-output implementations can subclass
`Step`, register declared outputs in `context[name]`, and implement `export(context)`.

`estimate_memory(inputs, params, profiles)` returns two non-negative Python integers:
`(workspace_bytes, output_bytes)`. Workspace is additional temporary working storage;
inputs are already accounted for. Include all new output tensors and metadata in
the second estimate. The inherited estimator is a conservative fallback, not an
algorithm-specific bound. Improve it for operations with large scratch allocations.

The fixed run budget is selected once before execution. The runtime updates
estimates from actual sizes, admits each step, and may spill evictable cached data.
An active NumPy allocation cannot be interrupted or spilled; underestimating an
algorithm's scratch space can still exhaust memory. A CUDA capability declaration
does not allocate GPU memory or implement a CUDA kernel.

The explicit `flat-reduction-v1` and `dense-writer-v1` resource contracts remain
unchanged under descriptor protocol v2. Both bundled and wheel providers
use these contracts. Bare capability booleans without the corresponding protocol
and hooks are rejected. See [package/resource protocol](package_protocol.md).

## Compatibility and persistence

All 64 Steps and 15 Readers publish protocol v2 without schema injection or a
`legacy_parameters` bypass. Their IDs and YAML entry points are unchanged. New plugins import from
`biopipe_sdk`, avoiding dependencies on private engine modules.

Graph v2 files accept optional `plugin_lock` entries containing package/version/
SHA-256. Saved graphs, nested route snapshots and launched jobs retain their pins.
Upgrading/removing a library plugin does not mutate an inserted route or a running
job. A graph with incompatible plugin generations fails explicitly. JSON routes
carry graph structure and contracts, but not Python code or input data.

See [SDK quickstart](sdk_quickstart.md), [SDK reference](sdk_reference.md),
[plugin lifecycle](plugins.md), and [agent interface](agent_api.md).

## Workflow configuration preservation

Graph v2 accepts optional `params` (pipeline globals), `runtime` (non-memory
runtime fields) and `manifest_extra` (additional top-level YAML fields). Missing
fields default to empty objects in v2. Older canvases must be migrated explicitly. The existing graph
`memory` field owns `runtime.memory` on export. An explicit disabled memory flag is
preserved; importing YAML without memory configuration retains CLI eager semantics.

Node `context_params` optionally overrides pipeline globals for that step. Route
expansion merges enclosing and route globals into this field, preserving independent
route instances. The runner exposes the merged values as `context.params` for the
step and restores outer context afterward. Data alias changes also rewrite builtin
`concat.align.key` and retention references. Arbitrary plugin-specific strings are
not guessed to be data references.

Configuration import and autosave no longer impose a fixed 2 MiB transport limit.
Graph structural limits (nodes, edges, nesting and tabs) remain validated. This is
independent of the optional scientific-data upload cap. CLI/MCP `configure` commands
can also edit `params`, `runtime` and `manifest_extra` atomically with undo.

## Stability policy

The authoring surface is `biopipe_sdk`. Operator IDs, parameter types, execution
defaults, output names, data contracts and resource hook signatures are a versioned
interface. Change an operator version when its behavior changes; change the major
version for incompatible parameter/port/default changes, and document migration.
Do not silently rename IDs or infer missing declarations. Keep metadata changes
separate from calculation changes in review. Protocol changes require regenerated
JSON schemas, updated examples and passing contract, packaging and execution tests.

Descriptor/package protocol 2, graph schema 2, workspace schema 1, data contract 1,
and the named resource protocols are separate version domains. Their numbers do
not need to match. New optional fields still require an SDK/schema update; arbitrary
unknown fields are rejected. Source scans and installs validate the same rules.
