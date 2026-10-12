# BioPipe Operator Protocol v1

Status: implemented for BioPipe Studio 0.2 and SDK 1.0. Python 3.11 or newer is required.
This document is the public contract for new Python plugins. Existing `Step`, `Reader`,
YAML tasks, graph v1/v2 files and route snapshots remain supported through adapters.

## Identity and discovery

A distribution exposes classes through standard Python entry points:

```toml
[project.entry-points."biopipe.operators"]
scale = "my_lab:Scale"

[project.entry-points."biopipe.readers"]
matrix = "my_lab:ArrayReader"
```

The class `name` is the stable registry ID, such as `my_lab.scale`. New plugin IDs
must contain a namespace separator (`.`), match `[A-Za-z_][A-Za-z0-9_.-]{0,79}`,
and be unique across readers and operators. IDs cannot shadow built-ins.
The entry-point key is not the operator ID. `version` uses three numeric components
with an optional prerelease or build suffix. The distribution version identifies
the installed wheel; an individual operator version describes its interface.

`biopipe plugin build` generates `biopipe-plugin.json` and embeds the same descriptor
in the wheel's `.dist-info/biopipe.json`, with an updated wheel RECORD. Installation
checks the descriptor against the implementation in a separate probe process.
Ordinary wheels built by other Python tools may omit this generated file; their
entry points are probed once during installation. The GUI reads JSON metadata and
never imports plugin Python. Built-in discovery runs once at service startup.

## Descriptor envelope

Every reader and operator has these fields:

| Field | Meaning |
| --- | --- |
| `protocol_version` | Exactly `1` |
| `id`, `version`, `kind` | Stable identity; kind is `operator` or `reader` |
| `entry_point` | Python `module:Class` |
| `title`, `description`, `category` | Display metadata |
| `parameters_schema` | Self-contained JSON Schema 2020-12 object schema |
| `contracts` | Version 1 input and output data contracts |
| `resources` | Supported memory modes, CUDA declaration, estimation hook |
| `implementation` | Installed package name, version and wheel SHA-256 |

Operators additionally expose `inputs_arity`, `outputs`, and `output_parameter`.
Readers expose `extensions`, `requires_siblings`, `excludes_siblings`, and
`handles_compression`. The registry retains legacy UI fields (`name`, `parameters`,
`runtime_defaults`, etc.) so the existing desktop can consume the same catalog.
Generated parameter forms support primitive fields, enums and JSON object/array
fields. Complex schema constraints are always checked by Python even when a custom
widget is unavailable.

Export machine-readable schemas with:

```text
biopipe schema operator
biopipe schema graph
biopipe schema workspace
```

Checked-in copies are in `biopipe_sdk/schemas/`. The descriptor envelope is
extensible; semantic validation also checks arity, parameter schemas and contracts.

## Parameters

New plugins must declare `parameters_schema`, including readers with no options.
The root must be an object. Use `additionalProperties: false` to catch misspellings.
Top-level property defaults are copied before validation. Nested defaults are not
materialized automatically. `$ref` and `$dynamicRef` may reference only local
fragments; validation never downloads remote schemas. Optional UI hints include
`title`, `default`, `enum`, `minimum`, and `maximum`.

Engine fields `output` and `_input_names` are not plugin calculation parameters.
The v1 dynamic output parameter is named `output`. Legacy built-in parameter
schemas remain permissive to avoid changing existing manifest behavior.

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
| `project` | Keep `keep_dims` and their annotations; optionally clear invalid semantics with `derived` |
| `declare` | Supply a complete inferred schema under `schema`; parameters may be referenced |
| `rename`, `transpose`, `concat`, `attach` | Use the corresponding established metadata operation |
| `unknown` | No static guarantee beyond runtime Form validation |
| `report`, `none` | No Form output; registering one is an error |

`declare.schema` uses inferred-schema maps (`labels: {dim: [names]}`,
`axis_info: {dim: [fields]}`, `info: {field: rule}`), not the input port's lists.
The `info` map on an output rule can add guarantees, including a new representation. A custom algorithm must
actually perform the declared transformation; a descriptor does not transform data.

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

Plugin v1 supports full-memory operator execution. New plugins declaring streaming
are rejected until a generic chunk protocol exists. Existing built-in streaming
implementations remain available and unchanged.

## Compatibility and persistence

The 31 existing Steps and 13 Readers publish this descriptor through adapters;
their names and YAML entry points are unchanged. New plugins import from
`biopipe_sdk`, avoiding dependencies on private engine modules.

Graph v1/v2 files accept optional `plugin_lock` entries containing package/version/
SHA-256. Saved graphs, nested route snapshots and launched jobs retain their pins.
Upgrading/removing a library plugin does not mutate an inserted route or a running
job. A graph with incompatible plugin generations fails explicitly. JSON routes
carry graph structure and contracts, but not Python code or input data.

See [SDK quickstart](sdk_quickstart.md), [SDK reference](sdk_reference.md),
[plugin lifecycle](plugins.md), and [agent interface](agent_api.md).
