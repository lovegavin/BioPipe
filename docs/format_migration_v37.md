# Static format declaration migration

SDK 3.7 makes port formats explicit for new declarations. Existing v3 revisions
remain readable; installing a newer application does not rewrite library source.

Inspect a trusted source directory without executing imports:

```sh
operon registry formats path/to/operators > format-review.json
```

The report separates proposals from `review_required`. Exit code 2 means that
review is needed, not that an unknown output was converted to Form. The scanner
uses literal protocol contracts and bounded output-flow inspection. The protocol
default port kind is Form; an explicit file kind remains FileArtifact. Declared
output schemas and known Form-preserving modes are authoritative. When those
contracts are insufficient, the scanner follows local aliases, trusted SDK/core
constructors, direct returns, context output writes and same-module helpers up
to four calls. Dynamic or mixed output paths remain review items. An annotation
alone does not override contradictory code. The tool never imports a scientific
implementation or infers matrix/list/sequence semantics. Report-only terminals
have no data output ports; native FileArtifact outputs remain file-backed.

Apply accepted proposals with `operon registry formats path/to/operators --apply`.
This is deliberately a partial migration: known proposals are applied, while
ambiguous classes stay unchanged and exit code 2 still requests review. The tool
stages replacement files, preserves original bytes in adjacent `.pre-sdk37`
backups and publishes each source by atomic replacement. A publication exception
rolls back already-replaced sources. Backups are never overwritten; retain them
for interruption recovery. Concurrent source edits block publication. A second
run skips already-migrated classes. Parameter JSON, workflow values, implementation
bodies and unrelated declaration fields/comments are not modified.

Review the diff and rebuild the selected library's static registry using its
SDK 3.7 maintenance environment (`operon registry build`, then
`operon registry check`). The apply command itself does not publish a new package
or rewrite an active profile registry. Test representative workflows before
publishing a separately versioned library. The command also works as
`python -m operon registry formats ...` in an installed headless application;
the source wrapper `scripts/migrate_format_declarations.py` is optional.

A Reader already returning Form needs no extra conversion or data copy. A Reader
returning native files needs a specifically supported parser/adapter; a filename
alone cannot establish a lossless file-to-Form conversion. New operators can
declare additional supported representations without changing saved parameters.

## Inspection evidence (2026-11-07)

These are dry-run snapshots, not a claim that all historical libraries were
migrated. No `--apply` was run on either library.

| Snapshot | Descriptors inspected | Proposals | Review required |
| --- | ---: | ---: | ---: |
| Tested 3.0.1 factory seed | 818 | 813 | 5 |
| Independent `library/main` source snapshot | 817 | 813 | 4 |

The factory seed tree is `f2e52a32e1c2d974562e9fda3f46b48339b39beb`.
The independent snapshot is commit
`ab1ce1dd97acc2dee5a3947ebb0ab3f51ea4e7a4`; its source resides under `src/`,
not `library/seed/`. The application worktree has no library source changes.

Factory review items are `analyze_contacts`, `export_results`, `order_axis`,
`select` and `sequence_stats`. Four have explicit Form/file polymorphic inputs;
`analyze_contacts`, `order_axis` and `select` also need output-flow review.
The independent snapshot has the same review set except `export_results`.
These entries stay on their supported legacy revision until a maintainer states
the actual capabilities; the tool does not narrow their interfaces to make the
review count disappear.

The [native Reader example](../examples/sdk37_native_reader/README.md) separately
verifies a no-copy mapped-array bridge and a legacy operator's numeric result.
