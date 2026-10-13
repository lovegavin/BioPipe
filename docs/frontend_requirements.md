# BioPipe Studio interaction and design

Studio turns YAML authoring into a local visual workflow: choose inputs, add nodes,
connect branches, set parameters, validate, run and inspect real outputs. The UI
remains primarily Chinese, retaining established abbreviations such as PCA, FDR,
MAF, HWE and LD pruning. Developer documentation is English.

## Workspace

| Area | Behavior |
| --- | --- |
| Top bar | Canvas tabs, save/import/export, Agent connection, validation and execution |
| Operator library | Searchable categorized JSON catalog; click/drag to insert; add saved routes; right-click management |
| Canvas | Input–operator–output node structure, typed connections, branching and ordered multiple inputs |
| Inspector | Double-click a node to inspect; catalog-driven parameters, source paths, dimensions and outputs |
| Execution settings | One automatic/manual run budget and emergency-spill options |
| Results | Actual statuses, planned/emergency/output persistence events, bounded previews, downloads and history |

Single-click selects and highlights related edges; double-click or focused Enter
opens the inspector. Selecting another node does not silently switch the inspected
node. Escape closes the inspector. Hovering/focusing input/output info bars shows
contracts and inferred metadata without loading the full matrix.

Shift-drag selects; Ctrl/Cmd-click toggles multiple selection. Middle-button dragging
pans, retaining existing background left-drag behavior. Ctrl+C/V copies nodes and
internal edges across tabs. Ctrl+X cuts, Ctrl+D duplicates, Ctrl+A selects all,
Delete removes selected items, Ctrl+Z undoes and Ctrl+Shift+Z redoes. Text fields
retain native shortcuts. `/` focuses library search. Ctrl+S explicitly saves a route;
it does not register an operator. Ctrl+Shift+T reopens a closed page.

Tabs retain independent graphs/viewports; double-click renames a tab and arrow keys
navigate adjacent tabs. Up to 20 pages can be open. All open pages and recently
closed pages are autosaved to the backend. Layout/viewport and panel preferences
are separate from analysis semantics. See [route operators](route_operators.md).

## Visual system

The workspace follows a restrained Linear/Vercel-inspired style: neutral surfaces,
local Geist fonts with system Chinese fallbacks, thin borders, clear type hierarchy
and layered panels. Panels overlap the canvas visually rather than forming one flat
surface. Menus/drawers use short transitions and visible keyboard focus; reduced
motion disables unnecessary animation.

Layout should provide the guidance. Use grouping, alignment, spacing, familiar
icons, restrained emphasis and visible state to make the next action apparent.
Avoid persistent instructional paragraphs, repeated subtitles and marketing copy
in the working canvas. An empty canvas uses a small branching diagram and a single
input action; package management lives in the library footer. Node cards show
file names or meaningful parameter summaries instead of operator descriptions.

Keep labels, units, required parameter semantics, errors and real run status
visible. Longer operator descriptions and shortcut reminders belong in contextual
help, available on hover, keyboard focus or click and dismissible with Escape.
Multi-file input requirements remain available in an expandable section. Budget
summary values describe the allocation policy, not a live memory measurement.
The allocation fraction comes from the backend (currently 90%). Studio shows a
numeric budget preview captured once at backend startup, replaced by the actual
budget when a run starts. There is no fixed byte cap or recurring free-RAM polling.
Every library category, including routes, can collapse independently. The browser
remembers its state; searching reveals matching categories and clearing the query
restores the previous layout.

Standard one-input/one-output nodes are 232×130 px with three layers. `nodeLayout.ts`
centralizes dimensions, port rows and measured positions. Unselected nodes have
soft multi-layer gray shadows; hover and selection deepen/enlarge them using a
240 ms opacity transition without moving ports. Ports are 12 px with larger hit areas.

Edges are 1.75 px normally and 2 px when highlighted. The 8×7 px arrowhead shares
the stroke color/scale. The curve ends at the arrow's tail; the arrow tip reaches
the target port along the terminal tangent. Only the line uses running-state dash
animation. A 22 px hit area eases selection. A fine 24/120-unit grid follows viewport
pan/zoom. Phosphor supplies shared icons; local SVG previews distinguish scatter,
histogram, line, Manhattan, Volcano, MA, heatmap, boxplot, survival and forest plots.
These are labeled visual examples, not generated analysis results.

Light, dark and system themes apply before first paint and are persisted separately
from workflows. The appearance menu supports arrows, Home/End, Enter and Escape.
At narrow widths side panels become drawers. Sidebars can be resized by dragging
their inner edge or using keyboard arrows; Shift accelerates, Home/End reaches bounds,
and Enter/double-click resets automatic sizing. At a typical 1440 px width the library/
inspector default to 208/272 px; large windows grow them while preserving at least
480 px of canvas when both are visible. Stored width preferences return after resizing.

## Graph and execution guarantees

Graph JSON is versioned and includes layout, parameters and memory settings. YAML
export/import preserves analysis semantics; YAML has no positions, so import lays
out the graph. Target port order determines operator input order. Compilation
rejects cycles, dangling edges, duplicate ports, wrong arity and duplicate output
aliases. A stable topological order is compiled into the existing serial executor;
visual branches do not imply parallel analysis.

Execution signatures ignore object key order, display titles and node positions.
Changing inputs, parameters, connections, plugin pins or memory settings marks old
results as stale. Measured UI dimensions are never stored as analysis configuration.

Built-ins use generated package and route indexes maintained with `biopipe registry`;
plugins add validated descriptors after successful installation. Parameter forms use schemas with JSON
fallbacks. The browser never scans Python. The API is loopback-only, with authenticated
writes and origin restrictions; each job runs in a separate directory/process.
Uploads stream to local files instead of base64 JSON. Optional formats need their
reader dependencies.

The worker selects its automatic memory budget once immediately before running. Real sizes,
RSS and spill records come from the manager; previews and figures come from actual
artifacts. Cancel terminates that worker and records cancellation. Intermediate
results are retained when explicitly requested. History can restore a job's graph.

## Agent integration

The Agent panel provides current-runtime MCP configuration, copyable selection
context and connection revocation. Agents receive selected graph structure and
contracts, not tensor contents. UI/agent writes share graph revisions and undo;
one external edit batch is one undo entry. Concurrent local edits are preserved in
recovery tabs. Graph edits do not run jobs. See [CLI/MCP](agent_api.md) for capabilities,
event cursors and client-side context behavior. No model provider is built in.

## Development and acceptance

```text
python -m pip install -e ".[agent,dev]"
cd frontend
npm install
npm run build
cd ..
python scripts/studio.py
```

Use Python 3.11+ and Node 22.12+. The default localhost port is 8765; `--port` selects
another. `npm run dev` proxies API requests to a separately running backend. Frontend
source builds update the development preview; copying those assets into the desktop
distribution is a separate release step.

The generated demo is a 128×24 CSV matrix with QC branching into PCA and describe.
Acceptance covers real insertion/wiring/editing, save/restore, cross-tab copy/paste,
invalid-graph diagnostics, actual worker results, contract popovers, CLI/MCP edits,
shared undo and Windows WebView2 startup/shutdown. Run `npm test`, `npm run build`,
the Python suite, and desktop verification for the relevant platform.

Default persistence is `~/.biopipe/studio/workspace/.studio`: `operators.json`,
`workflows/`, `assets/`, `plugins/`, `agent/` and isolated `jobs/<id>/` containing
`job.json`, `task.yaml`, `plugins.lock.json`, `console.log` and runtime outputs.
Drafts do not contain data and do not rewrite source task YAML automatically.

There is no cloud account system, general multi-user collaboration, cross-run
computation cache, globally optimal execution-order search or new CUDA kernel.
Existing reader/full-memory limitations remain in force.
