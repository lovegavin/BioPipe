# Reusable routes and multiple canvases

A route operator is a versioned graph of atomic operators. Before execution it is
expanded into the existing DAG, sharing the same info contracts and memory manager.
External connections replace its source placeholders.

## Interaction

1. Create tabs with the top-bar plus button; open saved routes from File. Up to 20
   tabs retain independent graphs and viewports. Double-click a tab to rename it.
2. Shift-drag selects a region; Ctrl/Cmd-click toggles node selection. Middle-button
   dragging pans the canvas; existing background left-drag behavior remains.
3. Ctrl+C/V copies nodes, parameters, internal edges and nested route snapshots
   across tabs. IDs and output aliases are regenerated; external edges are omitted.
   Text fields retain their normal keyboard shortcuts.
4. Ctrl+S saves a route with editable input names, output ports and ordering. Drafts
   may be incomplete. Saving alone never registers or updates a library operator.
5. The library plus button registers one or more saved routes. Registration requires
   complete compilable graphs and is atomic across the selected batch.
6. Right-click a library route or canvas route node to open its internal graph.
   An already open matching version is activated rather than duplicated.
7. File or Ctrl+Shift+T restores recently closed tabs. Open pages, viewports and the
   last ten closed pages are autosaved. A new UI session starts a fresh undo history.

Desktop and development startup share the same default profile. Explicit isolated
workspaces remain independent. Export/import route JSON to transfer a route to
another profile, then explicitly register it there.

## Graph protocol

Old `schema_version: 1` graphs still import. Saved/exported v2 graphs retain `name`,
`base_dir`, `nodes`, `edges`, `memory` and add an `interface`:

```json
{
  "version": 1,
  "inputs": [{"node_id":"matrix","label":"Expression matrix","contract":{"ndim":2,"dims":["sample","feature"]}}],
  "outputs": [{"node_id":"pca","handle":"out","label":"PCs","contract":{"ndim":2,"dims":["sample","component"]}}]
}
```

This is an interface fragment, not a complete graph. Real contracts also include
guaranteed info, labels and axis annotations. Inputs correspond one-to-one with
internal sources; their order defines `in-0`, `in-1`, etc. Original source paths
are not read when the route is invoked through external inputs. Outputs can expose
intermediates or be empty for a report-only route. By default, data outputs not
consumed by another data-producing node are exposed; report branches do not hide them.

`kind: "route"` nodes carry a complete `route: {id, version, name, graph}` snapshot.
One output uses `out`; multiple outputs use `out-0`, `out-1`, etc. Optional
`plugin_lock` entries retain wheel identities inside each graph. A transferred route
does not depend on a remote registry, but its data and Python dependencies must be
installed separately. See [plugin versions](plugins.md).

## Storage and execution

- `workflows/route_<id>.json` stores the latest saved route; `registry.json` stores
  explicitly registered snapshots. Startup scans once; ordinary reads consult a
  small revision marker and reload only after changes.
- Saving increments the version and checks `expected_version`. Re-register to update
  the library. Existing inserted instances keep their snapshots; new insertions use
  the latest registered version. Replace an old instance explicitly to upgrade it.
- Expansion gives internal nodes, Form names and figure filenames independent
  namespaces, allowing repeated calls of the same route without collisions.
- All expanded steps share the outer memory budget, spill mechanism and stable
  serial topological order. Retained-data requests are merged; a subgraph does not
  start another memory manager.
- Static checks cover the route interface and internal graph. Runtime Reader/Step
  boundaries validate actual data. Job records retain the original nested graph,
  expansion order and route ownership of internal nodes.
- Limits: six nested route levels, 1,000 expanded nodes and 5,000 edges. Recursive
  routes, cycles, invalid ports and duplicate output references are rejected.

Default shared location: `~/.biopipe/studio/workspace/.studio/workflows/`.
`BIOPIPE_STUDIO_HOME` or `--profile-dir` changes the profile through one resolver.
File locks and atomic replacement protect writes across desktop/development servers.
No installation drive or username is hard-coded.

## Bundled routes and library management

First launch registers the 14 templates in `src/web/builtin_routes.json`:

| Route | Inputs | Outputs | Internal nodes |
| --- | ---: | ---: | ---: |
| BGEN Dosage QC | 1 | 1 | 9 |
| Sequence feature analysis | 1 | 3 | 10 |
| RNA-seq DE | 2 | 3 | 14 |
| Genomic interval analysis | 2 | 3 | 11 |
| Multi-omics integration | 2 | 2 | 15 |
| ML regression (multi-model) | 2 | 3 | 13 |
| 16S Microbiome | 2 | 9 | 24 |
| GO enrichment | 1 | 1 | 6 |
| ML classification (multi-model) | 2 | 3 | 13 |
| Proteomics DE | 2 | 2 | 12 |
| Survival analysis | 1 | 2 | 6 |
| GTF Annotation Analysis | 1 | 3 | 9 |
| Single-cell QC and clustering | 1 | 2 | 15 |
| GWAS | 3 | 2 | 19 |

Node counts include input nodes.

`biopipe registry build` discovers `routes/**/task.yaml` and `task.yml`, validates
the operators and generates the manifest. `scripts/build_builtin_routes.py` is a
compatibility wrapper; it contains no route list or default historical Git ref.
See [registry maintenance](registry_maintenance.md). Templates retain example group names, clinical fields and gene choices;
open their internal graph, adjust, save and register for your own data. Placeholder
input paths are replaced by external inputs. Research datasets are not bundled.

Right-click atomic operators or routes to disable/enable them. Disabled items cannot
be inserted, but existing graphs remain executable. Deleting an atomic item hides it
and can be reversed in the deleted-items view. Deleting a route removes its registry
snapshot but retains the saved graph for re-registration. The installation receipt
prevents deleted bundled routes from reappearing on restart. Preferences live in
`workflows/library_state.json`.

## Adapted analysis operators

The local framework incorporates algorithms from upstream revision
`ab439ab9af3a36220941d6a8b27c580a268b7c95`: minimum-expression filtering, normalization,
log transform, imputation, group comparisons (including DESeq2), KM, Log-rank, Cox,
Volcano, MA plot, Heatmap, Boxplot and Forest plot. TxtReader handles `.txt` and
`.tab`; TsvReader handles `.tsv`. Eight additional operators from revision `fa267bc46a30ee9c9483b7442ff119b9aefcf62c`
support the [16S template](microbiome.md). Later additions include axis/single-cell
operations and GO enrichment. All atomic operators and Readers have contracts
and metadata/resource adapters; the generated registry is the current inventory.

DESeq2 uses only the two selected groups of raw integer counts and defaults to one
process. Install `requirements-analysis.txt` for PyDESeq2/lifelines. These kernels
remain CPU full-memory implementations, with no implied CUDA/chunk capability.

Tests: `test_routes.py`, `test_upstream_operators.py`, `test_sdk_agent.py`, and
frontend `editing.test.ts` cover snapshots, multi-output branches, atomic registration,
actual calculations, metadata and historical plugin compatibility.
