# Migration to protocol v3

BioPipe 0.5.1 requires protocol **3**. Graph schema **2** and workspace
schema **1** are separate versions and remain unchanged. Migrate a copy first.
Published v0.4.1 and the local protocol-v2 baseline remain available for comparison.

Each extension now owns a literal class `definition`, execution methods and a
separate parameter JSON named by `parameters_file`. There is no central parameter
authoring file and no runtime fallback to old class-level `parameters_schema`.

## Convert an extension without executing it

Export its old descriptor with the old SDK, then run:

```text
biopipe migrate path/to/operator.py --manifest old-provider.json
biopipe migrate path/to/operator.py --manifest old-provider.json --apply
```

The preview lists the Python and new `<module>.<Class>.parameters.json` files. Apply backs
up every affected original before publishing the code/JSON pair, and rolls back
a failed batch. It removes old declaration assignments, preserves execution methods,
and writes parameter defaults/UI hints into JSON. Review the pair, include JSON
in package data, then run `biopipe plugin check`, `test`, and `build`.

## Profiles and saved work

The current desktop source performs this backed-up conversion once, before
starting services, when the active profile uses a known older built-in protocol.
It preserves unfinished canvases even when required run parameters have not yet
been entered. Existing supplied values remain schema-checked; execution still
requires all mandatory parameters. Unknown protocols and old external wheels
stop startup with an actionable error and leave the originals intact.

The CLI remains available for previewing or explicitly converting a profile:

Close Studio and run `biopipe --profile-dir <profile> migrate` before adding `--apply`.
The Full Windows package includes the CLI: from the extracted folder, use
`runtime\python\python.exe -I -m biopipe migrate` to preview the default profile,
then `runtime\python\python.exe -I -m biopipe migrate --apply` to apply with backups.
No system Python installation is needed. Keep the previous release and its profile
backup until the migrated workflows have been checked.
Bundled v1/v2 profiles migrate with disabled/removed providers preserved. Historical
job folders and frozen locks remain untouched. External v1/v2 wheels must be rebuilt;
keep their old profile and install rebuilt wheels in a separate v3 profile before
migrating exported workflows. Migration cannot invent missing provider source.

New jobs validate code and declaration hashes separately. Parameter JSON edits can
publish a new descriptor without reinstalling code; retained snapshots keep their
own parameters. Source changes still need an explicit registry refresh/build.

## Individual graphs and YAML tasks

```text
biopipe migrate analysis.json
biopipe migrate analysis.json --apply
biopipe migrate task.yaml --apply
biopipe --profile-dir <v3-profile> migrate external-analysis.json --apply
```

Graph v1 converts explicitly to graph v2. Workspaces, nested routes, layout,
selection, source paths and memory settings are retained. Defaults are execution
defaults, not new-card UI presets. Missing operators or unsupported versions stop
the conversion before writing. Known numeric strings are normalized using the
schema. Standalone conversion uses bundled descriptors unless a v3 profile is
selected for external providers.

An old `draft.json` can seed a multi-document workspace once. The runtime then
uses only the workspace. The desktop examines only the explicitly resolved active
profile; it never searches other installations for profiles to migrate.
Old jobs and their outputs/logs remain historical evidence.
Agent selection and presence metadata remain unchanged; only their canvas and
undo/redo graph records are converted.

## Restoring a migration

Close Studio. Each backup's `manifest.json` records original paths and hashes.
Restore the original bytes; remove a newly created file only when its `backup`
entry is null. Run the matching old release with the restored profile.

The old `legacy/` tree and examples remain in Git tag `v0.4.1`; they are unnecessary
in the active tree. The current runtime accepts only protocol 3. Migration is an
one-time upgrade boundary, not an execution fallback or a bulk rewrite of past jobs.
