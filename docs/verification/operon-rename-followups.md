# Operon rename follow-ups outside the 5.0.0 library release

- Date: 2026-11-07
- Repository: `/home/gavin/BioPipe-4.0` (worktree), branch `release/5.0`, commit `706e537c`
- Working tree: uncommitted global `BioPipe` → `Operon` rename (2824 paths)
- Scope: migration work that is **not** part of building or verifying the 5.0.0
  operator library. This file is the only change made for this report.
- Status: investigation only; no rename, build, CI run, tag or commit was
  performed.

The 5.0.0 library itself is internally consistent: registry check reports 867
operators, 108 Readers, 7 packages, 72 routes and 0 errors. The items below are
repository, CI and application-release work that must happen around it. The
"Blocks 5.0.0?" column in the checklist means "blocks publishing the 5.0.0
library release"; application-only items are marked "No (app)".

## 1. GitHub repository rename

Current state:

| Item | Value |
| --- | --- |
| Git remote | `git@github.com:lovegavin/BioPipe.git` |
| Repository links in the tree | Already `github.com:lovegavin/Operon` |
| Badges | None in `README.md` (lines 1-12) |
| Tracked references to the old URL | None found by `grep -rn "lovegavin/BioPipe"` |

The documentation was renamed ahead of the repository. The links that already
use the new name are `README.md:34,147,184,190,363,420,431`,
`QUICKSTART.md:32,45`, `QUICKSTART.zh.md:27,40`, and
`.github/workflows/library-release.yml:33,39`. `README.md:363` is the repository
URL; `README.md:420,431` are clone commands.

Sequence for the repository admin:

1. Confirm the account can rename and that no automation depends on the old
   name during the window.
2. Rename with `gh repo rename Operon --repo lovegavin/BioPipe`, or use
   **Settings → General → Repository name**.
3. In the main checkout (`/home/gavin/BioPipe`, see section 2), run:

   ```bash
   git remote set-url origin git@github.com:lovegavin/Operon.git
   git remote -v
   git fetch --prune
   ```

   Linked worktrees share `.git/config`, so one update covers all of them;
   verify each checkout regardless.
4. Update external clones, CI variables/secrets that store the full repository
   name, badges, documentation sites and package metadata outside this tree.
   `GITHUB_REPOSITORY` in Actions changes automatically with the rename.
5. Re-run the release workflow's checkout/clone steps once, before tagging.

Redirect caveat: GitHub redirects web, Git, API and release-download URLs from
the old name after a rename. The redirect is not permanent and stops if the old
name is reused by another repository. Do not leave an old `origin` URL in
service just because it still resolves; update it and use the new URL in new
logs and checksums. Existing published links in the v3.0.1 release body still
contain `/BioPipe/`; those are historical and rely on the redirect.

## 2. Git layout and the standalone 5.0 tree

### 2.0 Status update (2026-11-07, local rename executed)

The local half of this section has now been executed, without committing or
tagging anything:

- `/home/gavin/BioPipe-4.0` was moved to `/home/gavin/Operon` with
  `git -C /home/gavin/BioPipe worktree move /home/gavin/BioPipe-4.0 /home/gavin/Operon`.
  It is still a linked worktree of `/home/gavin/BioPipe`, branch `release/5.0`,
  base commit `706e537c`, with the uncommitted 5.0 work intact.
- The conda environment `biopipe` was renamed to `operon`
  (`/home/gavin/miniconda3/envs/operon`); the interpreter and the editable
  `operon` package still resolve, `operon registry check --json` reports
  867 operators / 108 readers / 7 packages / 72 routes with `errors: []`, and a
  route still runs from the new path.
- Documentation references to the old environment path were rewritten to
  `envs/operon`.

Still pending, in order: rename the GitHub repository and update the main
checkout remote (section 1), commit the 5.0 work on `release/5.0`, push the
branch, then create the standalone clone at `/home/gavin/Operon` with the
sequence below. Until that clone exists, the moved directory must not be deleted
or treated as independent.

### 2.0.1 GitHub rename attempt (2026-11-07, blocked by token scope)

- The 5.0 tree is committed as `3686fee8` on `release/5.0` and pushed to the
  current remote (`git@github.com:lovegavin/BioPipe.git`); the branch is visible
  as `release/5.0` on the old repository name.
- A fine-grained token with `Contents: Read and write` was tried:
  `GET /user` and `GET /repos/lovegavin/BioPipe` succeed and report
  `permissions.admin = true` for the user, but
  `PATCH /repos/lovegavin/BioPipe {"name": "Operon"}` returns
  `403 Resource not accessible by personal access token`, and
  `POST /user/repos` returns the same 403. The token therefore lacks
  **Administration: Read and write**, which GitHub requires for rename/create.
- Rename paths: (a) GitHub web UI: repository Settings -> General ->
  Repository name `Operon` -> Rename (old URLs redirect); then
  `git remote set-url origin git@github.com:lovegavin/Operon.git`.
  (b) Issue a fine-grained token with Administration: Read and write and rerun
  the API call.
- The token must not be stored in the repository, docs or shell history; it is
  supplied per command through the environment and revoked by the user after
  the release.

Current layout:

| Path | Role | Commit |
| --- | --- | --- |
| `/home/gavin/BioPipe` | Main worktree, branch `main` | `d8727732` |
| `/home/gavin/BioPipe-3.0` | Worktree, `release/3.0.0` | `4ad16fe9` |
| `/home/gavin/BioPipe-4.0` | Worktree, `release/5.0` | `706e537c` |

`/home/gavin/BioPipe-4.0/.git:1` is not a directory; it contains
`gitdir: /home/gavin/BioPipe/.git/worktrees/BioPipe-4.0`. The 5.0 tree therefore
depends on the admin repository under `/home/gavin/BioPipe`.

Branch state:

- `main` has no upstream; local `main` is `d8727732`, while `origin/main` is
  `706e537c`.
- `release/3.0.0` currently tracks `origin/main` and is behind it; that upstream
  is wrong for the branch.
- `release/5.0` has no upstream and there is no `origin/release/5.0` head.
- There are 376 tags. The newest application tag by creation date is `v3.0.2`;
  `v4.0.0` is the newest 4.x application tag. The newest library tag is
  `library-v4.0.4`. **There is no `library-v5.0.0` tag** locally or on the
  remote, and `docs/releases/library-v5.0.0.md` does not exist.

Git has no `git worktree promote` subcommand. There are only two real choices:

- `git worktree move /home/gavin/BioPipe-4.0 /home/gavin/Operon` moves the
  directory and keeps the dirty tree, but it **remains a linked worktree** of
  `/home/gavin/BioPipe`.
- Clone plus copy produces a standalone repository. This is the option implied
  by "make the 5.0 tree standalone at `/home/gavin/Operon`".

Recommended standalone sequence:

```bash
# 1. From the admin repo, point it at the renamed remote.
git -C /home/gavin/BioPipe remote set-url origin git@github.com:lovegavin/Operon.git
git -C /home/gavin/BioPipe fetch --prune

# 2. Create the standalone clone.
git clone git@github.com:lovegavin/Operon.git /home/gavin/Operon
git -C /home/gavin/Operon checkout release/5.0   # after the branch is pushed

# 3. Copy the dirty working tree (tracked edits and untracked files), excluding
#    generated and local state. The clone's .git is preserved.
rsync -a \
  --exclude='.git' --exclude='build' --exclude='workdir' \
  --exclude='.local' --exclude='node_modules' --exclude='dist' \
  --exclude='.studio' \
  /home/gavin/BioPipe-4.0/ /home/gavin/Operon/

# 4. Compare before deleting anything.
git -C /home/gavin/Operon status --short | wc -l
git -C /home/gavin/BioPipe-4.0 status --short | wc -l
git -C /home/gavin/Operon diff --stat | tail -1

# 5. Only after the copy is verified, retire the old worktree.
git -C /home/gavin/BioPipe worktree remove --force /home/gavin/BioPipe-4.0
git -C /home/gavin/BioPipe worktree prune
```

If the admin directory is also renamed (for example to
`/home/gavin/Operon-admin`), run `git worktree repair` from the new location and
check the `gitdir` files in the remaining worktrees. Setting a new path is not
enough; every linked worktree stores its admin path.

Metadata and tags to fix after the move:

```bash
git -C /home/gavin/Operon branch --set-upstream-to=origin/release/5.0 release/5.0
git -C /home/gavin/BioPipe branch --set-upstream-to=origin/main main
git -C /home/gavin/BioPipe branch --set-upstream-to=origin/release/3.0.0 release/3.0.0
```

Do not create `library-v5.0.0` until the 5.0.0 commit, release note and CI fix
are in place. When ready, use an annotated tag and push the tag explicitly:

```bash
git tag -a library-v5.0.0 -m "Operon Operator Library 5.0.0"
git push origin library-v5.0.0
```

The tag is the release trigger and must point at the commit whose
`library/release.json` is 5.0.0. Moving a published tag is not an acceptable
repair.

Local and remote paths outside Git:

- `D:\BioPipe-4.x` exists on this machine as an older pre-rename checkout
  (`biopipe/`, `biopipe_sdk/`, `biopipe_studio.egg-info`). No tracked file refers
  to it. Move it to a neutral name such as `D:\Operon-5.x` by cloning or copying
  the working tree; do not copy a worktree's `.git` file without its admin repo.
  Update IDE workspaces, terminal profiles, shortcuts and scripts that point at
  the old directory.
- The server workdir `/public/home/lihj/biopipe-verify-4x` is not referenced in
  tracked files. Rename it to `/public/home/lihj/operon-verify-5x` (or create a
  symlink during the transition) and update SSH configs, job scripts and
  verification notes. The existing naming convention is shown by
  `docs/verification/library-3.0.1-remote.md:3`, which uses
  `/public/home/lihj/operon-verify-301`.

## 3. CI and release plumbing

`.github/workflows/library-release.yml` builds the library against the
application version in `library/release.json:4` (`build_application`, currently
`3.0.1`). The relevant step is `:33-41`.

### 3.1 Hard break: the application wheel name

The workflow assumes the application wheel is named
`operon_studio-${version}-py3-none-any.whl`:

```text
:33  wheel_url=.../v${version}/operon_studio-${version}-py3-none-any.whl
:34-36  curl; if that fails, build from the tag
:39  git clone --branch v${version} .../Operon.git .release-application
:41  python -m pip install .release-wheel/operon_studio-${version}-py3-none-any.whl
```

For `version=3.0.1`, that file does not exist. The v3.0.1 tag's project name is
`biopipe-studio` (`git show v3.0.1:pyproject.toml:6`), and the published v3.0.1
release assets are:

- `biopipe_studio-3.0.1-py3-none-any.whl`
- `biopipe_builtin_library-2026.11.6.1-py3-none-any.whl`
- `Operon_Setup.exe`
- `Operon-3.0.1-Server.zip`

There is no `operon_studio-3.0.1` asset. The URL returns 404, the fallback builds
`biopipe_studio-3.0.1-...whl`, and line 41 then fails on the hard-coded
`operon_studio` path. The job stops before the library build.

Fix options, in order of preference:

1. Resolve the application wheel from the release assets instead of assuming a
   distribution name (try `operon_studio-*`, then `biopipe_studio-*`, or query
   the release API).
2. In the fallback, install the built wheel by glob:
   `python -m pip install .release-wheel/*_studio-${version}-py3-none-any.whl`.
3. Publish a new application release under the `operon-studio` name and raise
   `build_application` to that version. Do not rename or replace the published
   v3.0.1 assets in place.

### 3.2 Hard break: missing release note

The publish job uses (`:107-110`):

```bash
gh release create "$GITHUB_REF_NAME" --verify-tag --latest=false \
  --title "Operon Operator Library v${GITHUB_REF_NAME#library-v}" \
  --notes-file "docs/releases/${GITHUB_REF_NAME}.md" \
  artifacts/*.operon-library.zip ...
```

For `library-v5.0.0`, `docs/releases/library-v5.0.0.md` is absent.
`--notes-file` fails before any asset is uploaded. Add the release note in the
same commit as the 5.0.0 version bump and before pushing the tag. The rest of the
command is valid after the rename: `--verify-tag` requires the tag to exist,
`--latest=false` keeps the application release as "latest", and the title strips
the `library-v` prefix correctly.

The remaining asset arguments are generated by the build (`*.whl`,
`*.operon-library.zip`, `*Routes*.zip`, `verification-*.json`, `SHA256SUMS.txt`)
or already exist (`QUICKSTART.md`, `QUICKSTART.zh.md`, `install_dependencies.py`,
`install-dependencies.sh`, `install-dependencies.ps1`). Confirm the
`install_dependencies.*` names after any packaging cleanup.

### 3.3 Artifact paths and least common ancestor

`upload-artifact@v4` (`:73-82`) uploads only paths under `build/library/`.
Artifact v4 computes the least common ancestor of the listed paths and preserves
paths relative to it. Because every path is under `build/library/`, the
download keeps that layout and the publish step can use `artifacts/*`.

Keep new upload paths under `build/library/`. Adding `frontend/dist` (created at
`:71` but not uploaded) or a repository-root file would move the least common
ancestor to the repository root and silently change every path under
`artifacts/`, breaking the `gh release create` globs. The
`download-artifact@v4` settings (`pattern: library-*`,
`merge-multiple: true`, `:88-92`) are otherwise correct.

`.github/workflows/assemble-release-asset.yml:15-16` uses the `GH_REPO`
environment variable and does not hard-code the repository, so it survives the
rename.

## 4. Operon Studio release surface

These items are not needed to build the 5.0.0 library, but they decide whether a
renamed application release is usable.

### 4.1 Distribution name and version

The working tree declares `name = "operon-studio"` and `version = "3.0.1"`
(`pyproject.toml:6-7`; `frontend/package.json:4`). The published 3.0.1 tag
declares `name = "biopipe-studio"` (`git show v3.0.1:pyproject.toml:6`).

Do not build and publish the renamed tree as application `3.0.1`. It would be a
different distribution with the same version, so pip, installer checks and
release assets would disagree. Choose one policy:

- keep the old distribution name for the 3.0.1 line, or
- publish the renamed application as a new version (for example `3.0.2` or
  `4.0.0`), with a release note describing the package rename.

The library release does not require an application version bump; the
application release does.

### 4.2 Packaging and installer

The desktop packaging already uses Operon names:

- `scripts/build_desktop.ps1:1` parameters; `:4` output defaults to
  `dist\Operon Studio`; `:18` builds `desktop\OperonStudio.csproj`; `:24` writes
  `operon-desktop.json`; `:28` emits `Operon Studio.exe`.
- `scripts/build_setup.py:76` emits `host/Operon_Setup.exe`.
- `docs/windows_setup.md:3` names `Operon_Setup.exe`; `docs/rebranding.md:9`
  records the same policy.

No tracked installer name still says `BioPipe`. The follow-up is to rebuild and
re-sign the installer after the distribution-name decision, then verify
shortcuts, uninstall registry keys and the `%LOCALAPPDATA%\Programs\Operon
Studio` default still match the new package.

### 4.3 Seed pin in the application release

`scripts/package_release.py:61` copies `library/seed` into the application
payload. `docs/releases/v3.0.0.md:52` records that the application ships a
tested seed (2026.11.6.1 for 3.0.1), not every later library release. The v3.0.1
release asset `biopipe_builtin_library-2026.11.6.1-py3-none-any.whl` confirms
that pin.

A future application release must pin its seed explicitly and state it in the
release note. Do not let a rebuild pick up an arbitrary `library/seed`; the
5.0.0 operator library is an independent release and may be newer than the seed
inside a given installer.

### 4.4 Profile, registry and runtime paths

Current defaults:

| Surface | Current | Old (HEAD) |
| --- | --- | --- |
| Studio profile | `.operon/studio` (`src/web/profile.py:61`) | `.biopipe/studio` |
| Profile override env | `OPERON_STUDIO_HOME`, `OPERON_STUDIO_DATA` (`src/web/profile.py:49-50`) | `BIOPIPE_*` |
| Runtime config | `OPERON_RUNTIME_CONFIG` or `.operon/runtime.json` (`operon/runtime.py:25`) | `BIOPIPE_RUNTIME_CONFIG` / `.biopipe/runtime.json` |
| Registry cache | `<data>/plugins/registry.json` (`operon/plugins.py:116`) | same relative layout under `.biopipe` |
| Workspace `.studio` | `~/.operon/studio/workspace/.studio` (`docs/plugins.md:12,21`) | `~/.biopipe/...` |

This machine already shows the split: `~/.biopipe` contains the old admission,
`runtime.json` and `studio`, while `~/.operon` contains only a new admission.
Nothing migrates the old profile automatically; users see an empty workspace and
must re-add operators unless they move the data.

Migration is a product decision. If continuity is intended, do it once while
Studio is closed:

```bash
# WSL/Linux; adjust names if the old profile was customised
test -d ~/.biopipe/studio && test ! -e ~/.operon/studio && \
  mv ~/.biopipe/studio ~/.operon/studio
test -f ~/.biopipe/runtime.json && test ! -e ~/.operon/runtime.json && \
  cp ~/.biopipe/runtime.json ~/.operon/runtime.json
```

On Windows the equivalent paths are `%USERPROFILE%\.biopipe\...` and
`%USERPROFILE%\.operon\...`. Merge, do not overwrite, when both exist. If
continuity is not intended, say so in the release note and remove the
`OPERON_STUDIO_HOME` guesswork from support replies.

### 4.5 `biopipe` CLI and Python import compatibility

The current tree has only the `operon` script:

```toml
# pyproject.toml:18-19
[project.scripts]
operon = "operon.cli:main"
```

There is no `biopipe/` package. The pre-rename tree had both aliases:

```toml
# git show HEAD:pyproject.toml
operon = "biopipe.cli:main"
biopipe = "biopipe.cli:main"
```

This contradicts the stated policy. `docs/releases/v3.0.0.md:3` says
"Compatibility Python modules, CLI aliases, MCP tool identifiers and serialized
format identifiers retain their existing names", and the HEAD policy table
(`git show HEAD:docs/rebranding.md:10-15`) listed `biopipe`, `biopipe_sdk`,
`biopipe` CLI and `biopipe_*` MCP names as retained. The current
`docs/rebranding.md:11-15` has been rewritten to say `operon` is the branded
alias, which is self-referential and no longer describes compatibility.

Decide explicitly:

- **Compatibility path (recommended for the 3.0.1 line):** add a small
  `biopipe` package that forwards imports and `python -m biopipe`, and restore
  `biopipe = "biopipe.cli:main"` in `[project.scripts]`. Add tests that
  `biopipe --help` and `python -m biopipe` reach the same service.
- **Breaking path:** bump the application major version and rewrite the 3.0.0
  claim. Do not ship the current tree as 3.0.1 with a promise the code does not
  keep.

`docs/rebranding.md:12` currently says only that "the `operon` command is the
branded alias"; that sentence should name `biopipe` as the compatibility alias if
the first path is chosen.

### 4.6 MCP tool and resource identifiers

Current registrations start at `operon/mcp_server.py:14` (`operon_guide`) and
continue with `operon_sessions`, `operon_context`, `operon_graph`, and the rest.
The pre-rename registrations used `biopipe_*` (`git show HEAD:biopipe/mcp_server.py:14`).
There are no alias tools or alias resources.

`docs/agent_api.md:178-190` documents `operon_*` tools and `operon://...`
resources only. MCP clients cache tool names and users may have permissions tied
to them, so a rename is observable. Either register forwarding aliases with the
old names for the compatibility window, or treat this as a breaking application
release and say so. A silent rename is the worst option.

### 4.7 Workflow, archive and bundle format identifiers

Current identifiers:

- `operon/workflow_spec.py:14` — `FORMAT = 'operon.workflow'`.
- `src/web/api.py:255` — import accepts only `format == 'operon.workflow'`.
- `operon/library_bundle.py:57` — bundle format `operon.library`; `:67` writes
  `Operon-Library-v{version}.operon-library.zip`; `:90` requires the format.
- Route archives are exported/imported as `.operon.zip`.

The pre-rename values were `biopipe.workflow` (`git show
HEAD:biopipe/workflow_spec.py:14`) and `biopipe.library`. A saved
`.biopipe.workflow`, a parameter/execution sidecar with the old format marker, or
a `.biopipe.zip` route archive is rejected by the current readers. There is no
format alias.

Choose one: add legacy readers that accept both markers and rewrite on save, or
provide a migration command and document that old files need conversion. For
bundles, the legacy filename/format gap is already recorded in
`docs/verification/operon-5.0.0-compatibility.md:143-155`; this follow-up must
also decide whether `.biopipe-library.zip` stays in the picker.

The bundled provider IDs changed as well: `library/seed/operon/builtin_packages.json:6`
and the other package entries use `operon-*`, while the pre-rename file used
`biopipe-*` (`git show HEAD:library/seed/biopipe/builtin_packages.json:6`). The
bundle manifest has no `replaces` field (`operon/library_bundle.py:60-67`), so
test a 5.0.0 bundle installed into a 3.0.1 profile before assuming the old
`biopipe-*` providers are replaced rather than duplicated.

### 4.8 Documentation regressions introduced by the rename

These are content bugs, not counts. They should be fixed in the migration, but
they are outside this report's single-file scope:

- `README.md:19` — "Operon (formerly Operon)" (HEAD: "formerly BioPipe").
- `docs/README.md:3` — "Operon, formerly Operon".
- `docs/rebranding.md:3-4` — "Operon is the earlier product name" (HEAD:
  "BioPipe is the earlier product name").
- `docs/rebranding.md:12` — "the `operon` command is the branded alias"
  (HEAD: `biopipe` was the existing command and `operon` the branded alias).
- `docs/rebranding.md:32-33` — "older Operon installations" and
  `.operon/profiles` (HEAD: BioPipe and `.biopipe/profiles`).
- `docs/releases/v3.0.0.md:3` — "Operon Studio is now **Operon Studio**".

The first and third bullets are the clearest regressions: they make the rename
historically false. Fix them with the actual previous name, not with a synonym.

## 5. Checklist

"Blocks 5.0.0?" asks whether the item blocks **publishing the 5.0.0 library**.
Items needed only for a future application release are marked "No (app)".

| Item | Current | Required | Owner | Blocks 5.0.0? |
| --- | --- | --- | --- | --- |
| GitHub repository rename | `lovegavin/BioPipe` | Rename to `Operon`, keep redirects | Repo admin | Yes |
| `origin` URL | `git@github.com:lovegavin/BioPipe.git` | `.../Operon.git` in all worktrees | Repo admin | Yes |
| Documentation links and badges | Already `/Operon`; no badges | Keep new URLs; add badges only with new URL | Docs | No |
| CI application wheel | Expects `operon_studio-3.0.1`; only `biopipe_studio-3.0.1` exists | Resolve both names or publish a new app wheel | CI/release | Yes |
| Release note | `docs/releases/library-v5.0.0.md` absent | Add note before tagging | Release manager | Yes |
| `library-v5.0.0` tag | Absent locally and remotely | Annotated tag on the 5.0.0 commit | Release manager | Yes |
| Application distribution name/version | `operon-studio` 3.0.1; published 3.0.1 is `biopipe-studio` | Keep old name or bump version | App maintainer | No (app) |
| `biopipe` CLI/import shim | Removed | Restore shim or declare breaking release | App maintainer | No (app) |
| MCP identifiers | `operon_*` only | Aliases or documented break | App maintainer | No (app) |
| Workflow/format readers | `operon.*` only | Legacy readers or migration command | App maintainer | No |
| Profile/runtime cache | `.operon` only; old `~/.biopipe` ignored | Migration or explicit fresh-profile policy | App maintainer | No |
| Provider IDs in bundle | `operon-*`; old seed `biopipe-*` | Test replacement vs duplication on 3.0.1 | App maintainer | No |
| Legacy library archive | Picker accepts, installer does not | Route or remove suffix | App maintainer | No |
| Windows checkout | `D:\BioPipe-4.x` | Re-clone/move to `D:\Operon-5.x` | Infrastructure | No |
| Server workdir | `/public/home/lihj/biopipe-verify-4x` | Rename or symlink to `operon-verify-5x` | Infrastructure | No |
| Seed pin | 2026.11.6.1 in 3.0.1 | Pin explicitly in the next app release | Release manager | No |
| Installer/package names | Already Operon | Rebuild and re-sign after version decision | Release manager | No |
| Rename text regressions | Six self-referential statements | Restore BioPipe as the former name | Docs | No |

## 6. Verification and limits

Commands used for this report:

```bash
git remote -v
git worktree list --porcelain
git branch -vv
git ls-remote --heads origin
git ls-remote --tags origin 'library-v5*'
git tag --sort=-creatordate | head
git show v3.0.1:pyproject.toml
grep -rn "lovegavin/BioPipe\|lovegavin/Operon" README.md QUICKSTART.md QUICKSTART.zh.md .github
```

The v3.0.1 asset names were confirmed against the published GitHub release; the
repository has no local copy of those assets. No rename, build, CI run, tag or
commit was performed. The local paths `D:\BioPipe-4.x` and
`/public/home/lihj/biopipe-verify-4x` were checked only where they exist on this
machine; the server path is not referenced in tracked files, so its rename is a
manual infrastructure step.

The 5.0.0 library compatibility evidence is in
`docs/verification/operon-5.0.0-compatibility.md`. This report deliberately does
not repeat the 946-file `data_formats` trial or the registry counts; it covers
only what the rename still needs outside that library release.

## 2.1 Status update (release preparation, 2026-11-07)

- GitHub repository rename is complete (`lovegavin/Operon`); `origin` points at
  the new URL and both `main` and `release/5.0` are pushed.
- Tag `library-v5.0.0` is pushed (annotated, commit `3686fee8`).
- Release assets are built and validated in `build/release-5.0.0/` (10 files;
  `sha256sum -c SHA256SUMS.txt` passes for all 9 checksummed artefacts).
- The GitHub Release itself is **not created yet**: the provided fine-grained
  token returned `401 Unauthorized` (it was masked in chat and has likely been
  revoked). Creating the release needs a token with **Contents: Read and write**
  or a manual upload from the asset directory.
