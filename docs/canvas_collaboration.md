# Live canvas collaboration and script editing

Operon 3.0 uses the existing document service as the source of truth for both
Studio and agent changes. A desktop window is not required for an agent to edit
a persisted session. Opening a workspace with the same document IDs resumes its
latest session and displays edits made while Studio was closed.

## Read a small change stream

Start with `operon_sessions` and `operon_context`. Use a session's event cursor
to request incremental updates with `operon_events(session_id, after, limit)`.
The equivalent HTTP endpoint is:

```text
GET /api/agent/sessions/{session_id}/events?after=0&limit=20
```

The response includes:

| Field | Meaning |
| --- | --- |
| `seq` | Current stream head, not necessarily the end of this page |
| `next_cursor` | Cursor to use for the next request |
| `has_more` | More retained events follow this page |
| `reset` | Requested history expired or cursor is ahead of the server |
| `revision` | Current scientific/document revision |
| `events` | Bounded event list with actor, transaction ID and compact previews |

Always advance using **`next_cursor`**, not `seq`. Deduplicate by `seq`. On
`reset`, re-read the current context/document and rebuild the local projection;
do not assume the retained events represent all previous edits. Each session
retains 200 events. Requests accept 1–100 events; previews show at most eight
changed fields and 160 characters per value. Selection/presence changes have
their own UI revision and do not invalidate scientific execution identity.

Read more detail only when needed:

```text
GET /api/agent/sessions/{session_id}/transactions/{transaction_id}?offset=0&limit=20
```

MCP exposes the same operation as `operon_transaction_diff`. It returns keyed
paths, previous/new values, truncation flags, total count and `next_offset`.
Values are previews, not executable patches: a large code value can be truncated.
Retrieve the node/document to inspect its complete current source. Expired
transaction details return `history_expired` (HTTP 410).

## Write and undo one transaction

Apply an operation batch with the expected document revision and a stable
`request_id`. The server assigns the committed `transaction_id`. A stale revision
returns a conflict without changing the document. Retrying an accepted request
with the same payload returns its
receipt and `replayed: true`; it does not apply the changes twice. Actor identity
comes from the authenticated server context, never from a caller-supplied label.
Graph, event and receipt are persisted in the same atomic session-file update.

`operon_undo` accepts an optional `transaction_id`. A targeted undo checks that
the fields touched by that transaction still contain its result, then reverses
those fields as a new transaction. Later unrelated user edits are preserved.
Overlapping edits, dangling edges or cycles return a conflict instead of
restoring an obsolete whole-document snapshot. Older pre-3.0 history without
field preconditions only supports its latest undo entry. Retained undo history
is bounded to 30 entries per document.

Editing permission does not grant execution permission. Saving code, changing
parameters, copying templates and undoing a transaction never launch a job.
Starting a job remains an explicit separate operation under execution scope.

## Studio activity

The canvas Activity control displays user and agent transactions. Expand an
entry to view the real before/after values; click its path to locate the node.
Recent agent edits briefly highlight affected cards without moving the viewport
or changing the user's selection. **Undo this edit** uses the same conditional
transaction undo as MCP. A conflict is shown inline.

Studio polls the compact stream and requests the complete workspace only when a
document revision changes. Concurrent local edits are retained; if they cannot
be merged, Studio keeps a recovery tab and a local recovery copy rather than
silently replacing the user's work.

## Temporary scripts in Studio

Drop `.py`, `.R`, `.c`, `.cc` or `.cpp` files onto the canvas. Static inspection
creates a script snapshot; it does not execute/import the script or install its
dependencies. Other dropped files use the existing Reader upload path, keeping
multi-file datasets in the same batch. A failed script inspection creates no
partial canvas edit.

Script nodes open in **Code** view. Edit the display name in the inspector.
**Save and inspect code** validates and commits the code; supported Python
literal assignments can then be explicitly selected and **Extracted to parameter
JSON**. Source, schema and frozen parameter values change together, so one undo
reverses the extraction. An asynchronous save refuses to overwrite a newer code
edit. The **Parameters** view uses the declared JSON schema. Saved routes retain
their own values; changing a default does not alter them.

Native operators and Readers also offer Code view, but their installed source
is read-only. Missing or compiled-only source is reported as unavailable. A
route operator shows its frozen graph instead of claiming to be standalone
source. This UI does not rewrite installed Python packages.

Expand **Save to operator library** to choose a stable namespaced ID (for example
`lab.trim_reads`) and a category. **Save reusable operator** builds and installs
a v3 provider with its own parameter JSON and Markdown documentation, then
refreshes the catalog. This explicit install never runs the analysis or installs
its scientific dependencies. Existing IDs are rejected rather than overwritten;
the original script node and saved route snapshot stay intact.

Right-click a node's input/output row or individual port to copy a file adapter
template for Python, R, C or C++. The template accepts `--in-data` and
`--out-result`, declares matching named file ports, and initially copies the
input bytes. Replace that copy with the intended analysis. Only explicitly
declared file formats are offered. A Form/matrix port needs an explicit output
or conversion operator first; a template never infers a matrix-to-list semantic
transformation. Current graph script nodes require exactly one file output.

Environment readiness, dependency isolation, execution logs and memory budgets
are handled by the shared runtime. Static inspection does not make arbitrary
user code streaming-safe or memory-bounded; the operator author must implement
those properties in the script itself.
