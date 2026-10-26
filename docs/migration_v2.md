# One-time migration to protocol v2

This development version uses SDK 2.0, descriptor/package protocol 2 and graph
schema 2. Workspace and data-contract versions remain 1. The published v0.4.1
release is unchanged. Keep that release and its profile for historical replay.

All 64 bundled operators and 15 Readers already declare their parameter schemas,
data contracts and presentation. Built-in IDs, algorithms, streaming reductions,
disk Readers, fixed run budgets and emergency spill behavior are retained.
`legacy_parameters`, UI-JSON schema injection and function-source default inference
have been removed. Unknown descriptor fields are rejected.

## Before opening an existing profile

Close Studio instances using the profile. First evaluate the new source with a
separate profile:

```text
python scripts/studio.py --profile-dir biopipe-v2-test
```

Relative profile names are relative to your home directory; they are never relative
to the checkout or EXE. An explicit absolute profile path works on every machine.
The normal default is still `~/.biopipe/studio`. No startup scan searches other
profile folders or silently migrates files. Invalid workspaces fail visibly.

Preview conversion, then apply it to the same explicitly selected profile:

```text
python -m biopipe migrate --profile-dir <profile-directory>
python -m biopipe migrate --profile-dir <profile-directory> --apply
```

The first command does not write files. The second saves original bytes and a
SHA-256 manifest under `<data-directory>/migrations/v2/<timestamp-id>/` before
publishing changes. A failed batch restores the files it wrote. Running the tool
again makes no changes to an already converted profile.

Migration converts saved and registered workflow snapshots, nested routes,
workspaces and agent session/undo graphs. It preserves selection, layout, source
paths, route IDs, globals, node context parameters and memory configuration.
An old single-page `draft.json` can seed the workspace once. The runtime stores
only the multi-page workspace afterward. Disabled or removed bundled providers
stay disabled or removed. Completed jobs, their logs, outputs and old installation
snapshots are historical evidence and are not rewritten.

An external provider built under v1 must be rebuilt and validated under v2. The
tool refuses to replace such a mixed profile blindly. Keep the v1 profile, install
rebuilt providers into a separate v2 profile, then convert exported workflows with
that profile selected. Source files and wheel dependencies are not automatically
modified during profile migration.

## Individual graphs and YAML tasks

```text
python -m biopipe migrate analysis.json
python -m biopipe migrate analysis.json --apply
python -m biopipe migrate task.yaml --apply
python -m biopipe --profile-dir biopipe-v2-test migrate external-analysis.json --apply
```

File backups go to `.biopipe-migration-backups/<timestamp-id>/` beside the input.
The selected v2 profile supplies external operator declarations. Without a profile
selector, standalone file conversion uses the bundled declarations. Missing
operators and unsupported schema versions stop the conversion before writing.

Conversion materializes execution defaults, not new-card UI presets. PCA without
`n_components` therefore becomes `n_components: 10`, although a newly dragged card
suggests 2. Known numeric strings are converted according to the schema, such as
`target_sum: 1e6` to a JSON number. It never guesses unknown parameter meanings.
For new YAML use `1.0e+6` or `1000000`, which PyYAML recognizes as numeric.

## Author source declarations

Prefer updating the class using the [Step](step_extensions.md) or
[Reader](reader_extensions.md) guide. For a v1 source whose old generated descriptor
is available, the static converter can insert its declared parameter schema:

```text
python -m biopipe migrate my_step.py --manifest old-biopipe-plugin.json
python -m biopipe migrate my_step.py --manifest old-biopipe-plugin.json --apply
python -m biopipe plugin check ./my_extension
python -m biopipe plugin test ./my_extension
python -m biopipe plugin build ./my_extension
```

The converter parses Python without importing it, matches classes to descriptor
IDs, preserves method bodies and removes `legacy_parameters`. Review schemas,
input/output contracts and defaults before building. It does not invent missing
biological contracts or rewrite imports. Source-directory authors run
`python -m biopipe registry check` and `build` after adapting the declaration;
installed users click **Refresh library** after updating their source modules.

The final public manifest contains `id`, `entry_point`, `parameters_schema`,
`contracts` and `resources` exactly once. Do not copy HTTP catalog projections
(`parameters`, `runtime_defaults`) or installation fields (`implementation`,
`distribution`, `execution`) into an author descriptor. Rebuild wheels from source;
changing only a v1 manifest's version number is insufficient.

## Restoring a migration

Close Studio. In the migration backup, `manifest.json` lists every original path,
its backup filename and hashes. Restore those original bytes; remove files whose
`backup` is null because the migration created them. Use v0.4.1 with the restored
profile. The new runtime intentionally has no v1 compatibility mode.

Historical source, generated example output and the old `legacy/` tree remain in
Git tag `v0.4.1`. They are not required in the active source tree or the new package.
`scripts/diagnose_pins.py` remains the read-only pin diagnostic; the obsolete
`repin_all.py` alias is removed. Migration is distinct from rewriting past jobs.
