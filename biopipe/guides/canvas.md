# Edit the user's canvas

1. `biopipe_context()` reads the current selection and immediate neighbors.
   With several windows call `biopipe_sessions()` and explicitly choose one.
   An empty selection is not permission to rewrite the whole document.
2. Use the returned session_id, document_id and revision. For a broader requested
   edit, explicitly request `scope="document"` or `biopipe_graph(session_id)`.
3. Submit all related changes together with `biopipe_apply`:

```json
{"session_id":"<session>","document_id":"<document>","expected_revision":4,
 "request_id":"edit-001","commands":[
   {"op":"update_node","id":"pca","patch":{"params":{"dim":"feature","n_components":3,"output":"pcs"}}}
 ]}
```

Replace IDs/revision and parameters with actual current values. `params` replaces
the entire object: preserve parameters you are not changing. Other commands are
add_node, remove_node, connect, disconnect and configure. A batch is one undo entry.
CLI: `biopipe --session <session> graph apply commands.json --document <document>
--expected-revision <revision> --request-id edit-001` (one command line).

4. On revision_conflict reread context and reconcile the user's changes. Reuse a
   request ID only for an identical retry. `biopipe_undo` reverses one transaction;
   it does not reverse an executed analysis or delete output files.
5. Run separately, only when authorized. `biopipe_run` requires run scope.

No open window? Use the workflow guide. Never fabricate a canvas session.
