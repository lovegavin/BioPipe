# Working with BioPipe

BioPipe has one current implementation on `main`. The archived pre-integration
main is historical source, not a second runtime or authoring protocol.

For operating the software, start with `biopipe help` (or MCP `biopipe_guide`),
then request only the needed task topic and operator schemas/document sections.
See `docs/agent_operations.md`; third-party application authors should use
`docs/api_quickstart.md` and its tested client example.

1. Read `README.md`, then the relevant page in `docs/README.md`. Search the
   operator catalog before opening implementations. Retrieve selected schemas
   and Markdown sections rather than loading the entire library into context.
2. Operators and Readers use SDK protocol v3: literal code declaration, separate
   parameter JSON, adjacent Markdown. Keep execution values in each workflow's
   independent JSON; never replace saved values with current defaults.
3. Use the shared application service for workflow preparation, validation,
   execution and artifacts. CLI, HTTP and MCP are adapters, not separate engines.
4. Canvas edits use revision checks and one coherent undoable transaction.
   Starting a job is a separate action requiring execution permission.
5. Preserve lazy registration, managed memory, disk/stream protocols, emergency
   spill, SSH, resumable transfers and host admission. Do not eagerly materialize
   data to discover its size or silently advertise chunking for full-mode code.
6. Validate schemas and paths before running. Do not invent data paths,
   biological conclusions, test evidence, dependency availability or review
   status. Never author the engine-owned `_input_names` parameter.
7. Rebuild the static registry and docs when authoring metadata changes. Run
   focused tests, then the relevant integration tests. Documentation changes
   alone must not change execution identity or require users to repin workflows.
8. Keep product paths portable and technical documentation in English. Do not
   commit credentials, local runtime state, generated jobs or private datasets.

Related process notes: remote installs and repair in
`docs/agent_environment_repair.md`, agent process rules and token
discipline in `docs/design/agent_working_notes.md`.

Application changes belong outside `library/seed/`. Operator/Reader code,
sidecars and template routes belong inside it. Preserve original v3 entry-point
names; do not raise the application version for library-only changes.
See `docs/application_library_boundary.md` and `library/README.md`.
