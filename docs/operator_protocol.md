# Operator protocol v3

BioPipe 0.5.0.dev0 uses SDK 3.0.0 and protocol 3. Operator IDs, numerical kernels,
Form contracts and resource protocols retain their existing meaning.

## Authoring unit: code + its own parameter JSON

Each operator or Reader owns two files, for example:

```text
pca.py
pca.parameters.json
```

The Python class contains a literal `definition` dictionary describing identity,
ports, resource capabilities, dependencies and presentation, plus its execution
methods. Its `parameters_file` points to a JSON Schema beside that module.
When omitted, the filename is `<module>.parameters.json` (`parameters.json` for
`__init__.py`). Multiple classes in one module must use distinct explicit filenames.
There is no centrally edited parameter document for the whole library.

This authoring JSON is a **schema**, not a workflow's mutable value file. Saving a
route freezes effective values for each node into its own parameter JSON; each job
also records its actual values separately. Defaults changed later apply to new or
otherwise unspecified values, not to an already saved route. See
[workflow parameter values](workflow_parameters.md) for storage and execution rules.

The parameter JSON is the only authoring source for parameter types, defaults,
validation limits and UI field hints. Do not duplicate `parameters_schema` or
`ui_defaults` on the implementation class. Use `params` in `Operator.compute`,
`ctx.step_params` in `Step.run`, or normalized Reader keyword arguments. The engine
validates parameters and supplies defaults before dispatch. A default is not a
required parameter; add a name to the schema's `required` array to require input.

See the complete [Step](step_extensions.md) and [Reader](reader_extensions.md)
examples. `biopipe plugin init` creates this file pair and an executable test.

## Definition fields

`definition` must be literal data: no function calls, imports or computed values.
Maintenance reads the Python AST and JSON; it never executes module top-level code.

| Field | Meaning |
| --- | --- |
| `protocol_version` | Exactly `3` |
| `id`, `version`, `kind`, `title` | Stable identity, semantic interface version, `operator`/`reader`, display title |
| `contracts` | Contract version 1, `inputs` list and `output` rule |
| `resources` | `memory_modes`, `supports_cuda`, optional stream/disk protocol |
| `inputs_arity`, `outputs`, `output_parameter` | Operator ports; dynamic output parameter is `output` |
| `extensions`, sibling/compression fields, `file_input` | Reader routing and input hints |
| `dependencies`, `dependency_imports` | PEP 508 requirements and optional import checks |
| `category`, `icon`, `preview`, title hints | Optional presentation; category supplies the default icon |

Use namespaced IDs for external providers, such as `lab.scale`. A bundled provider
can retain its existing IDs. `provider = "biopipe-core"` chooses ownership for a
source-library implementation; updates cannot steal another provider's IDs.
Entry points and hashes are generated, not written by authors.

## Operator categories and icons

Use `quality_control`, `analysis`, `data`, `visualization`, or a custom category in
`definition.category`. Package ownership does not determine the UI category.
Set `definition.icon` to a Studio icon name or a module-relative image path.
Relative PNG/JPEG/WebP/GIF/SVG icons remain supported. Include images and parameter
JSON files in wheel package data. Omitted or unknown named icons use category
artwork; a declared image path must exist and be included in the wheel.

## Dependency declarations

Use literal PEP 508 requirements in `definition.dependencies` and optional import
names in `definition.dependency_imports`. Package-wide requirements apply to every
entry. Keep conflicting requirements on their respective operators. The loader
uses one Python executable: compatible entries share dependencies; conflicts use
private directories and subprocesses. See [dependency isolation](dependency_isolation.md).

## One generated index, several consumers

`biopipe/builtin_packages.json` and profile `plugins/registry.json` are generated
indexes. They combine each class definition and its parameter JSON into a
snapshot descriptor. The frontend, graph compiler, contract checker, memory
planner, CLI and MCP consume that descriptor. Do not edit the generated index to
change an operator: edit its own files and refresh/build the registry.

The HTTP service imports no implementation modules. Workers lazily import only
used Steps and Readers; Reader suffix and companion routing use metadata first.
The loader creates a declaration-bound subclass, leaving other retained snapshots
unchanged. It does not restore the removed v1/v2 class-field fallback.

## Identities and updates

- `code_sha` hashes normalized implementation/helper Python source bytes. Parameter
  JSON and icons are excluded. The bundled library currently hashes its two small
  implementation trees together, conservatively invalidating cross-module helpers.
- `declaration_sha` hashes the canonical descriptor excluding the two hashes and
  installed-state fields. It includes the parsed parameter JSON and frozen icon.
- The wheel's package `sha256` is artifact provenance, separate from these identities.

Graph pins match execution identity, not `declaration_sha`. The declaration hash
remains an audit/integrity field in descriptors and locks:

| Provider | Graph matching fields |
| --- | --- |
| Installed wheel | Package, package version, wheel `sha256`, `code_sha` |
| Bundled v3 source | Package, package version, `code_sha` |

The bundled `sha256` fingerprints both the generated index and source bytes, so
rebuilding after a default change alters it too. It remains a cache/provenance
fingerprint but is not a graph compatibility key when `code_sha` is present.
Nested graphs use the same matching rule. A declaration-only rebuild needs no old
profile snapshots: portable routes keep their concrete values with the current
compatible schema. Wheel artifacts remain strict even when Python code is equal.

This is a compatibility contract, not automatic proof that arbitrary schema edits
are safe. Incompatible schema/port changes require a major operator version and a
package version bump before publication. A version change must go through the
refresh/installation transaction, not the metadata-only update API. Known bundled
code rebinding also refuses to cross operator or package versions. Parameter and
data-contract validation still runs before and during execution.

Frozen job locks are different from portable graph pins: workers verify both code
and declaration integrity and execute the complete descriptor stored for that job.
New graph resolution never rewrites old job locks, defaults or dependency paths.

Parameter-only refresh publishes a new metadata snapshot and reuses code paths,
dependency targets and bytecode. Changes to version, code, entry points, dependencies or
resource hooks use the installation transaction. Successful dependency checks
remain valid across parameter/presentation-only changes during the same session.

## Compilation and checks

Installation compiles code and dependency targets with the executing Python's
`unchecked-hash` bytecode mode before publication. Workers disable bytecode writes.
Full desktop packaging compiles sources with its bundled Python 3.11; Lite does
not ship interpreter-specific application bytecode. Development source remains
normal checked source; never precompile mutable development folders unchecked.

`biopipe registry check` validates schemas/contracts, checks literal parameter reads
against JSON properties, and compares the generated index. Unknown literal keys
are errors; dynamic keys and parameters forwarded to helpers generate warnings.
This is conservative static checking, not proof about arbitrary Python execution.
CI runs registry drift checking and tests. See [migration](migration_v2.md) before
using a v1/v2 profile or extension with this development version.
