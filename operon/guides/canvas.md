# Edit the user's canvas

1. `operon_context()` reads the current selection and immediate neighbors.
   With several windows call `operon_sessions()` and explicitly choose one.
   An empty selection is not permission to rewrite the whole document.
2. Use the returned session_id, document_id and revision. For a broader requested
   edit, explicitly request `scope="document"` or `operon_graph(session_id)`.
3. Submit all related changes together with `operon_apply`:

```json
{"session_id":"<session>","document_id":"<document>","expected_revision":4,
 "request_id":"edit-001","commands":[
   {"op":"update_node","id":"pca","patch":{"params":{"dim":"feature","n_components":3,"output":"pcs"}}}
 ]}
```

Replace IDs/revision and parameters with actual current values. `params` replaces
the entire object: preserve parameters you are not changing. Other commands are
add_node, remove_node, connect, disconnect and configure. A batch is one undo entry.
CLI: `operon --session <session> graph apply commands.json --document <document>
--expected-revision <revision> --request-id edit-001` (one command line).

4. On revision_conflict reread context and reconcile the user's changes. Reuse a
   request ID only for an identical retry. The receipt contains transaction_id;
   retries return the same ID without applying the edit twice. `operon_undo`
   accepts that transaction_id to reverse its fields while preserving unrelated
   later human changes. An overlapping later edit returns undo_conflict. Never
   resolve it by restoring an obsolete full graph. Undo does not reverse an
   executed analysis or delete output files.
5. Run separately, only when authorized. `operon_run` requires run scope.

No open window? Use the workflow guide. Never fabricate a canvas session.

`operon_open` defaults to `mode="replace"`. Use `mode="append"` when
opening a separate workflow tab, and `document_id` plus the current revision
when intentionally replacing an existing document. Never replace unrelated work.

## Follow changes without reloading the graph

Use `operon_events(session_id, after=cursor, limit=20)` for bounded user/agent
events, actor identities and short before/after previews. Continue at
`next_cursor`, not `seq` (the stream head). `has_more` means another page remains;
deduplicate by event seq. On `reset=true`, reread current context/graph because
retained history has a gap; do not reconstruct state from incomplete deltas.
Selection events change UI state, not the scientific graph revision.

For a relevant transaction only, call `operon_transaction_diff(session_id,
transaction_id, offset=0, limit=20)`. Continue at next_offset; previews mark
truncated values. Retrieve current source/node values when full content is
needed, never use a truncated preview as replacement code. Studio's Activity
panel shows the same changes and supports conditional Undo this edit.

CLI equivalents (one line each):

```text
operon --session <session> events get --after <cursor> --limit 20
operon --session <session> graph diff --transaction-id <id> --limit 20
operon --session <session> graph undo --document <document> --expected-revision <current> --transaction-id <id>
```

Code/parameter edits, event reads and undo never launch computation or repair
dependencies. Environment installation uses the workflow guide's explicit
prepare-environment action; job submission remains separate.
