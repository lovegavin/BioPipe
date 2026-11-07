# Operon 5.0.0 SDK and protocol compatibility

- Date: 2026-11-07
- Repository: `/home/gavin/BioPipe-4.0`, branch `release/5.0`, commit `706e537c`
- Scope: Studio 3.0.2 / SDK 3.7 compatibility for the 5.0.0 library.
  This page records the compatibility decisions, the applied SDK 3.7 migration and its evidence.

## Conclusion

Operon 5.0.0 targets **Studio 3.0.2 / SDK 3.7.0**. `protocol_version` stays the
integer `3`; the additive `protocol_revision: "3.7"` marker plus explicit
`data_formats.inputs/outputs` is now declared on 969 of the 974 bundled
descriptors (862 operators and 107 Readers). The five generic operators that
the SDK migration tool leaves for human review (`analyze_contacts`,
`export_results`, `order_axis`, `select`, `sequence_stats`) stay on their
supported legacy revision because their ports are Form/file polymorphic and
SDK 3.7 has no wildcard or union capability.

A graph may therefore contain both revisions. Edge analysis treats an edge with
a legacy side as *unresolved but permitted* instead of invalid, so the 72
builtin routes keep validating and executing; two declared 3.7 ports are still
checked strictly. Protocol tests (`test_contracts`,
`test_format_adaptation`, `test_static_format_migration`,
`test_manifest_v3`) pass: 73 passed. The registry reports 867 operators, 108
Readers, 7 packages, 72 routes and 0 errors.

## Versions in this tree

| Component | Version | Evidence |
| --- | --- | --- |
| Operon Studio application | `3.0.2` | `frontend/package.json:4`; `pyproject.toml:7` |
| Bundled operator library | `5.0.0` | `library/release.json:2-4`; `library/pyproject.toml:7` |
| Library application bounds | minimum/build `3.0.2` | `library/release.json:3-4` |
| Operon SDK | `3.7.0` | `operon_sdk/__init__.py` |
| Operator protocol | integer `3` | `operon_sdk/protocol.py:9` |

The Studio 3.0.2 tree ships SDK 3.7.0. The library version is independent of
the application version: 5.0.0 is a library-only release built and tested
against application 3.0.2.

## `protocol_version` stays 3

`PROTOCOL_VERSION = 3` is a single integer constant, and the descriptor field is
declared as `Literal[3] = 3` (`operon_sdk/protocol.py:9,32-35`). There is no
`protocol_version: 3.5` or `3.6`; the newer capabilities are expressed through
the optional string field `protocol_revision`, whose allowed values are `"3.5"`
and `"3.6"`.

A descriptor with neither `protocol_revision` nor the new optional fields is a
plain v3 descriptor and remains valid. SDK 3.6 accepts it unchanged.
This is why 5.0.0 can add a new library version without a protocol bump and
without requiring existing routes or operators to be rewritten.

## v3.5 localization is optional

Protocol v3.5 adds an optional language pack. A package opts in by keeping
`protocol_version: 3` and adding `protocol_revision: "3.5"` plus a
`localization` object. The SDK validation requires a revision in `{"3.5",
"3.6"}` when localization is present (`operon_sdk/protocol.py:288-296`), and
rejects the combination with the message `Language packs require
protocol_revision 3.5`.

The compatibility rule is deliberate (`docs/localization.md:72-77`):

- SDK 3.5 accepts existing v3 packages unchanged.
- Older SDKs are not expected to accept new v3.5 descriptors; the host or
  server must be upgraded.
- 5.0.0 does not require localization. Packages without a language pack stay on
  the plain v3 path.

## v3.6 `data_formats` is optional

Protocol v3.6 adds optional logical types and representation metadata
(`docs/data_formats.md:3-6`). It does not replace the v3 contract:

- `data_formats` is an optional descriptor field; when present, the descriptor
  must also declare `protocol_revision: "3.6"` (`operon_sdk/protocol.py:288-296`,
  message `data_formats requires protocol_revision 3.6`).
- Existing v3 and v3.5 declarations keep their previous contract path.
- The metadata describes logical types and concrete representations; it does
  not infer scientific meaning from a file extension, array shape or Python
  coercion. A matrix cannot feed a logical list even when both use an ndarray
  (`docs/data_formats.md:36-40`).

Adaptation is a whole-graph concern, not a per-operator convenience. A route
adapts only when both connected ports declare `data_formats`; otherwise the
converter returns the hard error `Both ports must declare data_formats before
format adaptation` (`operon/conversions.py:42`). The runtime builds an explicit
`conversion_plan`, supports `auto`, `disabled` and `fixed` edge policies, and
bounds the search to four conversions, 128 converters and 256 states
(`docs/data_formats.md:44-59`). Two conversions are initially executable:
`matrix.npy.write` and `matrix.npy.view` (`docs/data_formats.md:63-68`). The
converter registry is application-owned (`docs/data_formats.md:77-80`).

## The 946-file adoption trial and revert

The SDK 3.7 adoption used `operon registry formats library/seed --apply`. The
scanner proposed 970 descriptors (862 operators and 108 Readers) and reported
zero items it could not classify, but left the five generic operators above on
the legacy revision by design. `--apply` rewrote 969 source files with
`protocol_revision: "3.7"` and explicit `data_formats.inputs/outputs`, keeping
`.pre-sdk37` backups during the operation.

Adoption is only safe together with a coexistence rule. `operon/conversions.py`
returns `unknown` when one side of an edge has no `data_formats`; without a
rule that would invalidate every route that ends in the legacy
`export_results`. `src/web/contracts.py` now plans a conversion only when both
ports declare formats, so a legacy port makes the edge unresolved rather than
incompatible. A route that connects two declared 3.7 ports is still checked for
logical type, metadata and representation, and a real mismatch remains
incompatible.

The migrated tree passes `operon registry build --scope routes` and
`operon registry check --json` (867 / 108 / 7 / 72, errors 0), and a
representative route (`workdir/b46_route`, six steps, ends in
`export_results`) runs to completion. The five legacy operators are recorded
below; enabling them requires a wildcard/union port capability in the SDK.

## What 5.0.0 actually claims

- Base protocol: v3, unchanged; SDK 3.7 accepts it.
- Explicit SDK 3.7 port formats: enabled on 969 descriptors.
- Legacy revisions retained for five polymorphic generic operators, with a
  documented coexistence rule so mixed graphs remain valid.
- v3.5 localization: supported by the SDK but not enabled in this library
  because no translated operator corpus is maintained here.
- Registry verification: `python -m operon registry check --json` exits 0 with
  867 operators, 108 Readers, 7 packages, 72 routes and `errors: []`.
- Route execution verification: `workdir/b46_route` completes all six steps on
  the migrated tree.

## Library archive compatibility

The renamed build produces `.operon-library.zip` while the frontend and backend
still accept the legacy `.biopipe-library.zip` at the selection and upload
boundary:

- Frontend picker: `frontend/src/PluginPanel.tsx:54` accepts
  `.whl,.operon-library.zip,.biopipe-library.zip`;
  `frontend/src/AddOperators.tsx:46` shows both suffixes.
- Backend upload validation: `src/web/plugin_api.py:131-132` accepts both
  suffixes.
- New bundles are written as
  `Operon-Library-v{version}.operon-library.zip` with
  `format: "operon.library"` (`operon/library_bundle.py:57,67`), and
  `unpack_bundle` requires that format plus protocol 3 and the minimum
  application (`operon/library_bundle.py:90`).

Installation is not name-level only. `operon/plugins.py:313-321` routes a
bundle to `install_bundle` only when the filename ends in
`.operon-library.zip`. Any other upload falls through to `_install_many`, which
requires a `.whl` file and raises `Install a built .whl package; use plugin
build for a source directory` (`operon/plugins.py:341-348`). A legacy
`.biopipe-library.zip` therefore passes the picker and upload validation but
cannot be installed end to end; a legacy archive also carries
`format: "biopipe.library"` and would fail the format check even if it reached
`unpack_bundle`.

The honest statement is: **selection and upload accept both suffixes;
installation currently supports `.operon-library.zip` only.** This gap is
recorded, not claimed as working compatibility. Closing it needs either legacy
suffix/format routing with an explicit migration path, or removal of the legacy
suffix from the picker. That decision is outside this audit.

## Evidence map

| Claim | Evidence |
| --- | --- |
| SDK 3.6.0, protocol 3 | `operon_sdk/__init__.py`; `operon_sdk/protocol.py:9` |
| Descriptor fields and literal protocol | `operon_sdk/protocol.py:32-35` |
| Revision/field validation | `operon_sdk/protocol.py:288-296` |
| v3.5 semantics and acceptance | `docs/localization.md:72-77` |
| v3.6 semantics, conversions, limits | `docs/data_formats.md:3-6,28-40,44-59,63-68,77-80` |
| v3/v3.5/v3.6 authoring overview | `docs/operator_protocol.md:1,7,48-52` |
| Port-declaration error | `operon/conversions.py:42` |
| Both archive suffixes accepted | `frontend/src/PluginPanel.tsx:54`; `frontend/src/AddOperators.tsx:46`; `src/web/plugin_api.py:131-132` |
| Bundle routing and format | `operon/plugins.py:313-321,341-348`; `operon/library_bundle.py:57,67,90` |

## Residual risks

1. Partial `data_formats` adoption is unsafe: the 946-file trial showed existing
   routes break as soon as typed and untyped ports meet. Any future attempt must
   cover generic operators and the whole connected graph before enabling.
2. Legacy `.biopipe-library.zip` is accepted by the UI but not installable.
   Users may see a file picker that accepts a file the installer rejects.
3. The registry check validates descriptors, not route execution. Conversion
   behavior is covered by unit tests, not by this audit.
4. The 946/28 figures are preparation-record evidence; the trial patch is not in
   the tree and cannot be replayed from this commit.

## Verification

```
/home/gavin/miniconda3/envs/operon/bin/python -m operon registry check --json
```

Exit code 0. Counts: operators 867, readers 108, packages 7, routes 72. Errors
and changed entries are empty. The bundled library therefore declares itself
consistently on the v3 path while SDK 3.6 remains available for packages that
opt into v3.5 or v3.6 explicitly.


## SDK 3.7 explicit port formats (trial and revert)

Studio 3.0.2 ships SDK 3.7 and the static migration command
`operon registry formats <dir> [--apply]`.

### What was applied

- `operon registry formats library/seed --apply` added
  `protocol_revision: "3.7"` and explicit `data_formats.inputs/outputs` to 969
  files (862 operators and 107 Readers). The scanner reported no unclassified
  items; five generic operators stayed legacy by design.
- Rebuilding routes first exposed 51 route-contract failures of the form
  `输入输出契约不兼容：Both ports must declare data_formats before format adaptation`,
  all caused by a legacy `export_results` at the end of each graph.

### Coexistence rule

`src/web/contracts.py` calls `plan_conversion` only when both endpoints declare
`data_formats` and at least one side is explicit. An edge with a legacy port is
left unresolved (the v3 behaviour) instead of being marked incompatible.
Declared-to-declared edges are unchanged: logical type, metadata and
representation mismatches still fail.

### Verification

- `operon registry build --scope routes`: exit 0.
- `operon registry check --json`: 867 operators, 108 Readers, 7 packages,
  72 routes, errors 0.
- Protocol tests: 73 passed.
- `workdir/b46_route`: six of six steps complete.
- Remaining legacy operators: `analyze_contacts`, `export_results`,
  `order_axis`, `select`, `sequence_stats`. Their Form/file polymorphism needs
  SDK wildcard or union ports; declaring a single type would silently narrow
  their real interface.

## Legacy persisted identifiers

The rename replaced user-visible names but kept reading the serialized
identifiers that older installations wrote. After the first rename pass the
strict readers rejected those files, which surfaced as
`Task parameter values do not match task.yaml` for every route saved before
the rename. The readers now accept both spellings:

- `operon.task-parameters` and `biopipe.task-parameters`.
- `operon.workflow` and `biopipe.workflow`.
- `operon.workflow-parameters` and `biopipe.workflow-parameters`.
- `operon.workflow-execution` and `biopipe.workflow-execution`.
- `operon.workflow-lock` and `biopipe.workflow-lock`.

New files are written with the `operon.*` identifiers. Legacy
`.biopipe-library.zip` packages stay selectable in the Studio import picker,
but installation continues to require the new `.operon-library.zip` bundle;
that asymmetry is intentional and documented in the rename follow-up list.
