# Frontend integration decisions

The unified application keeps the Studio desktop interface and its graph editing,
undo, keyboard shortcuts, middle-button panning, resizable panels, remote execution,
memory controls, job management and figure outputs. Operator metadata remains in
the v3 registry instead of a second frontend-specific operator table.

## Adopted from the upstream direction

- Six canonical categories: quality control, statistics, data preparation, machine
  learning, omics and visualization. Known English and Chinese aliases share one
  section and a stable collapse preference. Unknown custom categories retain their
  own names and sections.
- Readers are searchable by ID, title, description and file extension. Clicking or
  dragging a Reader creates an input node with that exact registered Reader ID,
  dimensions, label settings and parameter defaults. The inspector can change the
  Reader or return to automatic format detection. The Reader section starts
  collapsed and expands during search; a user's collapse choice is remembered.
- Operator and Reader descriptions appear in hover/help controls. Reader format
  details are collapsible. Cards retain compact titles and existing specialized
  artwork; optional package images and category-based fallbacks still work.
- Platform labels describe the execution requirement. Compatibility warnings use
  the selected execution target, not the editor's OS. A Windows editor can add and
  configure Linux-only operators for a Linux server. Automatic placement defers
  capability decisions to the execution planner.

## Intentionally not copied

- Unknown categories are not flattened into an `Other` group.
- Reader cards are not passive previews: their selection is persisted and honored
  by local imports, SSH inputs, contracts, dependency planning, pins and workers.
- Library cards do not gain permanent explanatory paragraphs or per-operator
  presentation overrides duplicated from the registry.
- Windows does not disable an operator merely because the operator runs on Linux.

## Explicit Reader routing

`source.reader` is an optional registered ID, separate from `source.args`. For
example, `reader: BedReader` selects a text BED reader even when PLINK companion
filenames are present. `reader: AlignmentReader` keeps a BAM as a file artifact for
Hi-C tools rather than materializing it through another BAM reader. An explicit ID
may override the extension (for example, a CSV parser for a custom suffix), but
compression support and required companion checks still apply.

Without a selector, automatic suffix and companion routing remains available.
Ambiguous formats require a selection; neither the UI nor the worker silently
chooses the first registered reader. A missing explicit Reader is an error. Saved
graphs and task YAML preserve the selection, while Reader argument values remain
in each graph's independent parameter JSON.

`TxtReader` has its own `args.reader` parser parameter. It is not the canonical
selector and is preserved for delegated text parsing.

## Importing task YAML

Studio retains workspace inputs and can locate task-relative inputs under the
configured software installation's `tasks/`, `routes/` and `examples/` directories.
It first checks the declared base and named task, then accepts a unique matching
directory. Multiple matches require an explicit base; import never silently picks
the first file. This uses directory and file metadata, not dataset contents.

The application's default input roots are the workspace and configured code root.
An explicitly configured `input_roots` list remains authoritative. Import, contract
checks, preparation, saved routes and execution use the same roots; resolved paths
and symlinks outside them are rejected. Output and cache paths remain confined to
the workspace. Existing input files are referenced directly, not copied. Windows
inputs on another drive retain an absolute path when relative export is impossible.

Task YAML that references a parameter sidecar still requires the complete route
bundle or CLI execution from its task directory; import does not discard frozen
parameter values.

Static registry generation uses `import_manifest(resolve_inputs=False)`. It keeps
the declared source and reference paths relative, even if matching input files
happen to exist on the build machine. Relocating the build must not change route
graphs or increment their versions; desktop import retains path resolution.
