# Operon 5.0.0 documentation audit

- Date: 2026-11-07
- Repository: `/home/gavin/Operon`
- Branch: `release/5.0`, commit `706e537c`
- Working tree: global `BioPipe` → `Operon` rename is uncommitted (5,417 files, 35,758 replacements)
- Scope: release and bundled-library documentation only. This audit changed no
  code, test or build files, and nothing was committed.

## Result

30 findings: 15 corrected in 7 documentation files, 15 recorded but not edited.
The unedited findings are either historical release notes, intentionally pinned
walkthroughs, or `BioPipe` → `Operon` rename artifacts that need an author
decision rather than a count/version edit.

## Verified release facts

| Item | Value | Evidence |
| --- | --- | --- |
| Application version | `3.0.2` | `frontend/package.json:4`; `pyproject.toml:7` (`operon-studio`) |
| Bundled library version | `5.0.0` | `library/release.json:2-4`; `library/pyproject.toml:6-7` |
| Library application bounds | `minimum_application`/`build_application` `3.0.2` | `library/release.json:3-4` |
| SDK version | `3.7.0` | `operon_sdk/__init__.py:8` |
| Operator protocol | integer `3` | `operon_sdk/protocol.py:9`; `:32-35` |
| Registry | 867 operators, 108 Readers, 7 packages, 72 routes, 0 errors | `python -m operon registry check --json` |
| Package entries | 975 descriptors | `library/seed/operon/builtin_packages.json` |

Package detail: `operon-core` 789, `operon-genetics` 21, `operon-expression` 13,
`operon-plots` 12, `operon-microbiome` 26, `operon-readers` 107, `operon-hic` 7.
The 975 entries equal 867 operators + 108 Readers. The entry counts mix both
kinds: `operon-readers` holds 104 Readers and 3 operators, `operon-hic` holds
4 Readers and 3 operators, and the other packages are operator-only.

The application version is intentionally still `3.0.2`. The 5.0.0 work is a
library-only change, and library releases do not raise the application version
(`AGENTS.md`; `docs/application_library_boundary.md`). The library declares the
application it was built and tested against instead.

The published `v3.0.2` tag records library `2026.11.6.1` (minimum application
`2.0.4`, build application `3.0.0`). The `5.0.0` library in this working tree is the next library release,
not a retroactive description of the published installer. Documentation must not
claim that the already-shipped 3.0.2 installer contains 5.0.0.

Registry command:

```
/home/gavin/miniconda3/envs/operon/bin/python -m operon registry check --json
```

It exited 0 with `operators: 867`, `readers: 108`, `packages: 7`, `routes: 72`,
`errors: []` and `changed: []`. The warning list is advisory parameter-read
metadata; it does not indicate a count mismatch.

## Severity

- **HIGH**: contradicts the current release identity or would mislead a user
  about what is bundled.
- **MEDIUM**: stale count or version on current guidance.
- **LOW**: stale example, tag or installer detail.
- **INFO**: correct for the historical version the page describes.

## Fixed findings

| ID | Location | Before | After | Severity |
| --- | --- | --- | --- | --- |
| F-01 | `library/README.md:5` | "Operon Operator Library v3.0.0" | v5.0.0 | HIGH |
| F-02 | `docs/package_protocol.md:14` | `operon-core` 394 | 789 | MEDIUM |
| F-03 | `docs/package_protocol.md:19` | `operon-readers` 97 | 107 | MEDIUM |
| F-04 | `docs/package_protocol.md:22` | "3.0.0 factory library: 717 operators and 101 Readers" | "5.0.0 factory library: 867 operators and 108 Readers" | HIGH |
| F-05 | `docs/library_releases.md:11` | Studio `v2.0.4` | `v3.0.2` | LOW |
| F-06 | `docs/library_releases.md:12` | `library-v2026.11.4`; "independent calendar version" | `library-v5.0.0`; independent library SemVer | MEDIUM |
| F-07 | `docs/library_releases.md:16-19` | 3.0.0 coordinated release; minimum/build `2.4.1` | 5.0.0 built and verified against 3.0.2; minimum/build 3.0.2 | HIGH |
| F-08 | `docs/library_releases.md:30` | "The v2.0.4 installer..." | "The current installer..." | LOW |
| F-09 | `docs/library_releases.md:36` | `...-v2026.11.4-Windows.operon-library.zip` | `...-v5.0.0-Windows.operon-library.zip` | LOW |
| F-10 | `docs/library_releases.md:58-59` | calendar `YYYY.M.D` scheme | independent library SemVer, e.g. `5.0.0` | MEDIUM |
| F-11 | `docs/library_releases.md:68-69` | tag and bundle `2026.11.4` | `library-v5.0.0` / `v5.0.0` | LOW |
| F-12 | `docs/installation.md:24-25` | 3.0.0 release integrates library 3.0.0 (717/101) | 3.0.2 line integrates library 5.0.0 (867/108); published installers retain their seed | MEDIUM |
| F-13 | `README.md:780` | "covers all 101 Readers" | 108 Readers | MEDIUM |
| F-14 | `docs/quickstart_full_flow.en.md:112` | 717 operators, 101 Readers | 867 operators, 108 Readers | MEDIUM |
| F-15 | `docs/rebranding.md:10` | Application version 3.0.0 | 3.0.2 | LOW |

All replacements were literal, asserted to have exactly one occurrence, and kept
the original line counts. A post-edit search found none of the superseded strings
in the edited files. `git diff --stat` reports more churn than these edits because
the uncommitted rename already touches every edited file.

## Recorded findings, not edited

| ID | Location | Statement | Why it was left | Severity |
| --- | --- | --- | --- | --- |
| N-01 | `docs/releases/v3.0.0.md:52` | The 3.0.0 application release "includes the tested 2026.11.6.1 seed" | Historical release page. The `v3.0.0` tag records library `3.0.0`; the sentence arrived in the 3.0.1 release commit `dcab7e59` and matches the `v3.0.1` tag (`2026.11.6.1`). Recorded rather than rewriting history. | LOW |
| N-02 | `docs/releases/v4.0.0.md:3,8,12-13,25` | Application 4.0.0, library 4.0.0, frontend 2.6.0, 717/101/7/24, "unified at 4.0.0" | Matches the `v4.0.0` tag; historical application line, later superseded by the 3.0.1 merge on `main`. | INFO |
| N-03 | `docs/releases/library-v4.0.0.md:9,36-38`; `library-v4.0.1.md:3,6,12,43`; `library-v4.0.2.md:3,6,35`; `library-v4.0.3.md:3,6,29`; `library-v4.0.4.md:3,12,30,35`; `library-v4.0.5.md:6,8` | `library-v4.0.0` is bundled with application 4.0.0 (minimum 2.4.1); `library-v4.0.1`-`library-v4.0.5` are quick-start notes for application/frontend 2.6.0. All list registry 717/101/7/24. | Historical for the 4.0.x library line; correct at their tags and superseded by library 5.0.0. | INFO |
| N-04 | `docs/README.md:77-79` | Index links the 4.0.0 release, 4.0.0 biological evidence and 4.0.0 discrepancies; no 5.0.0 note | No `docs/releases/v5.0.0.md` exists. Authoring a release note is outside this audit; the index should be updated when that note lands. | MEDIUM |
| N-05 | `QUICKSTART.md:1-7,21,66,109` | Application 2.6.0, library 4.0.4, 717/101/7/24 | Intentionally version-pinned walkthrough: the page says it is the "original, version-pinned library walkthrough" and that paths/dependencies describe 2.6.0. Its counts are internally consistent for 4.0.4. | INFO |
| N-06 | `QUICKSTART.zh.md:1-6,18,59,98` | Chinese translation of the same pinned walkthrough | Same reason as N-05. | INFO |
| N-07 | `docs/UNIFIED_MAIN.md:4,27-29` | Application 2.0.1, SDK 3.1.0, protocol v3, 717/101/24 | Historical integration snapshot; the page describes that merge, not 5.0.0. | INFO |
| N-08 | `docs/HIC_VALIDATION.md:15` | 67 operators, 19 Readers, 7 packages, 8 routes | Scoped historical Hi-C validation record. | INFO |
| N-09 | `docs/design/hard_queue_status.md:9`; `docs/design/hard_capability_status.md:265-343` | 673-689 operators, 101 Readers across v1.84.0-era snapshots | Running design logs; counts are dated observations, not current claims. | INFO |
| N-10 | `docs/minibinder_vhh_design_route.md:80` | "all 101 Readers are registered" | Design note tied to the library state at authoring time. | INFO |
| N-11 | `README.md:19` | "Operon (formerly Operon)" | Rename artifact: HEAD says "Operon (formerly BioPipe)". Naming, not counts/versions; needs an author decision. | HIGH |
| N-12 | `docs/README.md:3` | "Operon, formerly Operon, prepares..." | Same rename artifact as N-11. | HIGH |
| N-13 | `docs/rebranding.md:3-4,11-15,32-33` | "Operon is the earlier product name"; compatibility table lists `operon`/`operon_sdk`/`operon.workflow` as existing names; "older Operon installations ... `.operon/profiles`" | The rename rewrote the compatibility narrative into tautologies. HEAD says "BioPipe is the earlier product name" and "older BioPipe ... `.biopipe/profiles`". Fixing it requires deciding whether legacy names and paths are still supported. | HIGH |
| N-14 | `docs/OPERON_3_TEST_ACCEPTANCE.md:101,339` | "old Operon installation" | Historical 3.x acceptance evidence; the spelling is part of that record. | LOW |
| N-15 | `scripts/verify_release_agent.md:23` | "old Operon installation" | Outside the documentation tree; noted while checking rename consistency. | LOW |

## Historical pages deliberately untouched

The following describe named historical versions and were not edited:

- `docs/releases/v3.0.0.md`, `v4.0.0.md`, `library-v3.0.0.md`,
  `library-v3.0.1.md`, `library-v4.0.0.md` through `library-v4.0.5.md`
- existing `docs/verification/*` pages (biological evidence, biological issues,
  library 3.0.0/3.0.1 verification, routes 4.x) and `docs/validation/*`
- `docs/design/hard_queue_status.md`, `docs/design/hard_capability_status.md`
- `docs/HIC_VALIDATION.md`, `docs/UNIFIED_MAIN.md`,
  `docs/minibinder_vhh_design_route.md`

The uncommitted rename has already rewritten `BioPipe` to `Operon` in these
files; this audit made no further edits to them.

`QUICKSTART.md` and `QUICKSTART.zh.md` are also untouched, but for a different
reason: they explicitly present themselves as a pinned 2.6.0 / library 4.0.4
walkthrough. Changing only their numbers would produce a page whose installer
names, dependency notes and screenshots no longer match its text.

## Rename artifacts

The uncommitted global rename changed product-name statements, not just
identifiers. Four examples are current-tree regressions relative to HEAD:

- `README.md:19`: "Operon (formerly Operon)".
- `docs/README.md:3`: "Operon, formerly Operon".
- `docs/rebranding.md:3-4`: "Operon is the earlier product name" (HEAD: BioPipe).
- `docs/rebranding.md:32-33`: "older Operon installations" and
  `.operon/profiles` (HEAD: BioPipe and `.biopipe/profiles`).

These are HIGH-severity documentation defects, but they are outside the
count/version edit scope and cannot be fixed correctly without deciding whether
legacy identifiers, saved formats and profile paths remain supported. They are
recorded here for the rename review.

Related compatibility observation: a repository grep of `operon/*.py`,
`src/web/plugin_api.py` and `operon_sdk/*.py` found no remaining `.biopipe`
handling except the two upload/picker checks for the legacy archive suffix. The
legacy profile-path claim in `docs/rebranding.md` is therefore unverified.

## Verification

- Registry: exit 0, 867/108/7/72, no errors or changed entries.
- Package descriptor arithmetic: 789 + 21 + 13 + 12 + 26 + 7 + 107 = 975.
- Post-edit superseded-string search: empty.
- Edited files still have their original line counts.
- `git status` shows the two new audit files plus the pre-existing rename; no
  commit was created.

## Limits

This audit checked documentation against the working tree and release tags. It
did not execute routes, build installers, or validate the biological claims in
historical verification pages. It also did not author a 5.0.0 release note; the
missing index entry (N-04) remains until that note exists.
