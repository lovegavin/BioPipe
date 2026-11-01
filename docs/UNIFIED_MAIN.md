# Unified main integration

This source update establishes one current application and authoring protocol on
`main`. Application version: **1.1.0**. SDK version: **3.1.0**. Operator protocol:
**v3**. The latest previously published desktop binaries are a separate artifact;
this integration does not claim to have rebuilt or accepted a new Windows EXE.

## Source ancestry

- Application baseline: `8898d175bc8e7044cf881dee47ded5892ec9c74b` (Studio v0.8.3).
- Author's main snapshot: `9b6bbdd024fb4f59aa65b0850f72c36ec6df4538` (v0.115.0).
- Historical source: the `legacy-main-20261101` tag and its release ZIP preserve
  that complete main snapshot. It is not installed as a second runtime.

The integration preserves the desktop branch's existing 86 extensions, including
Hi-C file artifacts, streaming and disk readers, managed execution and unified
figure outputs. It adds 407 previously missing upstream extensions through an
explicit conversion to v3. The combined registry contains **410 operators and
88 Readers**, in seven independently manageable providers, and **24 route
templates**. Counts describe this integration, not hard limits in the software. Backend
**1.1.0** adds five population-genetics operators in `biopipe-genetics`; see
[the v1.1.0 release notes](releases/v1.1.0.md).

Coordinate precision fixes from upstream are applied to the existing CSV,
Parquet, BED, GFF3 and GTF implementations. Numeric columns retain float64 when
float32 would change their values. Shared machine-learning helpers no longer
construct parameter schemas during import; each concrete model owns its JSON.
Algorithms are not implicitly advertised as streaming or CUDA capable.

## Application boundary

`biopipe/application.py` composes workflow, task and artifact services over the
existing worker, SSH coordinator, memory admission and spill implementation.
`biopipe/control_api.py` exposes these through `/api/v1` in both Studio and a
loopback headless host. `biopipe/headless.py` owns discovery, startup and shutdown
without a canvas or frontend build.

- **API:** structured software integration, workflow revisions, durable task
  identifiers, bounded logs, artifact metadata and original output files.
- **CLI:** scripts, servers, reproducible commands and library maintenance. A
  detached service can continue after the submitting command exits.
- **MCP:** agent-oriented tools, selective operator documentation retrieval and
  optional live-canvas collaboration. Read/edit/run permissions remain separate.

No independent scheduler or scientific execution engine was introduced. Saved
workflows retain their own parameter and execution JSON. Submitted jobs freeze
their parameters and implementation pins. Request IDs protect retries from
accidentally submitting a second job; revision checks protect saved edits.

See [the API/CLI/MCP contract](headless_api.md) for commands, permissions,
error responses, service lifecycle and the limits of interrupted-job recovery.

## Authoring and discovery

Every bundled extension has code, an independent parameter schema JSON and an
adjacent Markdown document. [Protocol v3](operator_protocol.md) and the
[SDK guide](sdk_quickstart.md) are the canonical authoring instructions. New templates include
documentation; existing packages without a document still expose their schema.

Search returns compact indexed summaries. Detailed retrieval reads only selected
IDs and sections, optionally from a job's pinned library generation. Startup and
search use compiled metadata without importing operator modules or scanning their
source trees. Explicit registry maintenance validates and rebuilds that metadata.

Generated reference pages are marked as generated. They provide source-derived
usage, contracts and parameter references, not independent scientific review.
Authored guides and executable examples supplement them. Documentation-only and
nonbreaking default changes do not become new executable identities; workflow
values stay frozen. Wheel integrity still covers the complete archive.

## Frontend selection

The existing Studio layout, tab handling, selection/undo, remote controls, memory
settings and result views are retained. Adopted changes include canonical library
categories, searchable usable Reader cards, concise descriptions and execution-
target-aware platform hints. An explicit Reader selection survives save/export,
pinning, upload, SSH preparation and actual reading.

See [frontend integration decisions](FRONTEND_MERGE.md). Existing `TxtReader`
delegation parameters are distinct from the new optional `source.reader` ID.

The legacy incremental-test script and its duplicate reference-page gates are
not another maintenance path: the current static registry, documentation check
and focused pytest suites cover those responsibilities. Existing explicitly open
parameter maps remain compatible; new SDK templates use closed top-level schemas.
Publication heatmaps retain physical output dimensions instead of adopting a
new hardcoded matrix-cell limit. Resource admission remains the execution guard.

## Validation scope

The integration is checked with protocol, pin/default/documentation lifecycle,
managed-memory, disk/compression, CLI/MCP process, HTTP permission, SSH fixture,
frontend and public-data route tests. Optional dependency and real Linux-tool
tests report skips explicitly; local synthetic SSH fixtures are not a new
live-cloud acceptance run. See the [acceptance record](validation/UNIFIED_MAIN_0_116.md)
for concrete results and limits, rather than inferring coverage from the extension
count.

Five curated upstream public-data examples are retained in
`examples/route_combinations/`. Their own frozen parameter files and validation
notes distinguish executable regression checks from the author's biological
interpretations. Bundled template validation does not mean every possible
parameter combination or third-party tool has been scientifically validated.
