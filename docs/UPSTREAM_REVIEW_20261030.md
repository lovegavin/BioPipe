# Upstream review and application/library boundary

Checked upstream `lovegavin/BioPipe` main at
`9fccadb24624f9fffb8ab756fa730adbb9857fb2` on 2026-10-30.
The comparison uses common ancestor `3d57139167ee07428bf41276b84999feb84a06c0`.
No upstream merge or GitHub publication was performed.

## Frontend changes made upstream

Seven frontend files changed, with 80 insertions and 9 deletions:

| Files | Change |
| --- | --- |
| `App.tsx` | Synchronize the workflow import base directory after import |
| `Inspector.tsx`, `readerInput.ts`, `readerInput.test.ts` | Preserve source configuration when replacing a file; resolve an explicitly named Reader for its parameter form |
| `operatorPresentation.ts` | Add category aliases and presentation mappings for new operators |
| `package.json`, `package-lock.json` | Frontend package version metadata |

There are no upstream CSS, layout or canvas-art changes in this comparison.
Upstream lacks some later features of this release branch because the branches
diverged; that is not evidence the author deliberately removed those features.

The local application adopts import-directory synchronization and adapts file
replacement to its existing local/SSH and paired-FASTQ model. Same-Reader dimension,
label and non-file options are preserved. Newly uploaded companion paths replace
old paths, missing companions do not retain a previous file, and location becomes
local. A change of Reader uses the new format's defaults. The upstream generic
Reader-selector change was not copied over the local TxtReader delegate semantics.
Upstream presentation mappings will be considered together with adapted declarations;
the local library already supports declared categories and optional image icons.

## Operator library changes

Upstream's compiled index contains 144 operators and 40 Readers. This application's
current index contains 67 operators and 19 Readers. By ID, upstream has **80
operators and 24 Readers not present locally**. The exact inventory and entry
points are in [upstream_library_20261030.json](upstream_library_20261030.json).
This is an adaptation inventory, not a claim those entries were tested here.

Areas include enrichment/ssGSEA, ComBat, single-cell scoring and pseudobulk,
proteomics, association/meta-analysis, nonparametric statistics, regression and
projection methods, and additional sequencing/annotation/matrix Readers.

The upstream index/SDK still uses protocol 1 and inline class parameter schemas;
this application uses protocol 3 and individual parameter JSON files. A raw copy
cannot be a valid hot update. Shared IDs also need behavior review: upstream
`FastqReader` declares a Form-style output, while the Hi-C Reader here emits a file
reference suitable for streaming/external tools. Replacing it would break the
current FASTQ-to-Hi-C workflow. The local-only alignment/contact Readers and
`align_reads`, `build_contacts`, `analyze_contacts` are retained.

## What was separated

The engine, memory planner, desktop frontend, SDK, SSH integration and figure
viewer remain application responsibilities. Editable operator/Reader sources now
live in the persistent profile, independent of the EXE installation. Refresh or
whole-library import freezes providers into private immutable wheels, preserving
dependency isolation and stream/disk hooks. Installed independent libraries are
not replaced or augmented by factory-library changes during application upgrades.

The application still includes its factory library as a first-install/restore seed
and source-test fixture. This is an independent storage/update boundary, not a
claim that all factory source was removed from the application wheel or that a
second GitHub repository was created. Existing wheel-based third-party packages
keep their own installation lifecycle.

## Safe update workflow

1. Convert each new class into a v3 declaration and adjacent parameter JSON. Keep
   algorithm code where possible; verify contracts and actual resource hooks.
2. Review shared IDs before replacement, especially FASTQ and file references.
3. Run registry checks, numerical/format fixtures, memory-mode tests and route tests.
4. Build a versioned `.biopipe-library.zip`, separate from the application package.
5. Import that library in Studio. The existing transaction validates all providers
   and prepares dependencies before one active-registry switch. Frozen job locks
   and independent saved-route parameter values are retained.

The 80/24-entry adaptation is not included in this local application update.
