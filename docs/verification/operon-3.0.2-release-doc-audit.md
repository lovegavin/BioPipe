# Operon Studio 3.0.2 release documentation and license audit

Audit of the documents and bundles shipped by the **Studio 3.0.2** release
(`v3.0.2`), not of the 5.0.0 operator-library documents. Read-only audit: no
frontend source was modified, and no release asset was replaced.

Method:

- Files read at tag `v3.0.2` (README, `docs/README.md`, `docs/rebranding.md`,
  `docs/data_formats.md`, `docs/releases/v3.0.2.md`, installer sources).
- Release assets inspected from the published `v3.0.2` GitHub release:
  `VERIFICATION.md`, `SHA256SUMS.txt`, `Operon-3.0.2-Server.zip` (contents and
  checksums). The Windows Setup payload was not unpacked byte by byte; the
  installer sources were inspected instead.
- Severity: **blocker** = contradicts a shipped legal text or dead-ends the
  documented install; **high** = misleading or non-compliant for most users;
  **medium** = stale/confusing; **low** = polish.

## Summary

| Area | Findings | Blockers |
| --- | --- | --- |
| License / compliance | L1-L5 | L1 |
| Release documentation | D1-D8 | - |

Two findings are already fixed on `main` for the next release
(`docs/README.md` rename typo and SDK-version labels). README is owned by the
frontend release and is listed here as a required change for the frontend
release owner.

## License and compliance

### L1 (blocker) README License section contradicts the shipped Apache-2.0 license

`README.md` at `v3.0.2`, section `## License` (lines 1098-1104):

```text
Copyright (c) 2026 Haojian Li. All rights reserved.

This software is proprietary. No part of this software may be copied, modified, distributed, sublicensed, or used for commercial purposes without the prior written permission of the copyright holder.
```

The repository and both release bundles ship `LICENSE` (Apache License 2.0) and
`NOTICE` (Apache-2.0). A proprietary README notice cannot coexist with that
grant: users cannot tell which terms apply.

Required change in README (frontend release owner):

```markdown
## License

Operon is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE)
for the full text and [NOTICE](NOTICE) for attribution.

Third-party components are listed in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES/),
including the bundled pgenlib build and frontend dependencies. Commercial
support and custom development are available on request; they do not change the
open-source license of this distribution.
```

Also delete the "proprietary / prior written permission" wording and the
commercial-licensing sentence that implies a proprietary grant.

### L2 (high) Package metadata declares no license

No `license` field in:

- `pyproject.toml` (application wheel)
- `library/pyproject.toml` (operator library wheel)
- `frontend/package.json` (published shell package)

Suggested:

```toml
# pyproject.toml and library/pyproject.toml
license = { text = "Apache-2.0" }
```

```json
// frontend/package.json
"license": "Apache-2.0"
```

For the application wheel, also include the license files in the wheel:

```toml
[tool.setuptools]
license-files = ["LICENSE", "NOTICE"]
```

### L3 (high) Server bundle omits NOTICE and third-party notices

`Operon-3.0.2-Server.zip` contains `LICENSE` but no `NOTICE` and no
`THIRD_PARTY_NOTICES/` entries (verified by listing the archive). Apache-2.0
section 4(d) requires the NOTICE to accompany redistributions; third-party
attributions are also missing for recipients of the bundle.

Required: add `NOTICE` and the applicable `THIRD_PARTY_NOTICES/` files to the
server bundle root and to its `SHA256SUMS`, and copy them in `install.sh` next to
the installed application so they remain readable after installation.

### L4 (high) Windows Setup shows no license and installs none

`installer/Program.cs` and `installer/InstallFiles.cs` at `v3.0.2` contain no
license/agreement handling, and `scripts/build_desktop.ps1` references no
`LICENSE` or `NOTICE`. A Windows user therefore receives the binaries without
the license text or attribution.

Required:

- Show the Apache-2.0 license (or a license page linking to the installed
  `LICENSE`) before installation, and record acceptance if the installer already
  has an acceptance step.
- Install `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES/` into the application
  directory.
- Add an About/Help entry that opens `NOTICE`.

### L5 (medium, legal) pgenlib notice promises a source archive that is not shipped

`THIRD_PARTY_NOTICES/PGENLIB-WINDOWS.md` states that the modified pgenlib source
is included in the release assets. No pgenlib file exists among the `v3.0.2`
assets (`biopipe_studio-3.0.2-py3-none-any.whl`, `Operon-3.0.2-Server.zip`,
`Operon-Protocol-3.7.zip`, `Operon_Setup.exe`, checksums, `VERIFICATION.md`).

Required: either attach the corresponding source archive to the release (named,
checksummed, same version as the bundled binary) or correct the notice to state
the actual offer. Confirm first whether the Windows build really embeds pgenlib.

## Release documentation

### D1 (high) Stale maintenance-branch statement

`docs/releases/v3.0.2.md` (and the GitHub release body, which is identical)
says:

> Application maintenance continues on the existing `fix/3.0.1-installation`
> branch; ... `main` is retained but is not a maintenance/merge target for this
> release.

This is no longer true: `main` is the active release line and contains the 5.0.0
work. Replace with a statement that `main` is the maintained line, or drop the
branch paragraph from the release body.

### D2 (high) Dead CI link in VERIFICATION.md

`VERIFICATION.md` links:

`https://github.com/lovegavin/BioPipe/actions/runs/42367141220`

The repository was renamed; anonymous requests to the old path redirect for the
web UI but the literal URL is misleading in a release artifact. Use
`https://github.com/lovegavin/Operon/actions/runs/42367141220` (the run id is
preserved by GitHub's rename).

### D3 (medium) Bundled operator-library version is not stated in the release note

The 3.0.2 release note says only "the tested factory library is unchanged". The
bundle README says "unchanged independent operator library (2026.11.6.1)", while
`VERIFICATION.md` reports 717 operators / 101 Readers. Add one explicit line to
the release note:

> Bundled factory library: seed `2026.11.6.1` (717 operators, 101 Readers).
> Installing a newer library bundle does not change the application version.

This prevents users from assuming the 5.0.0 library (867 operators / 108
Readers) is included in the 3.0.2 installer.

### D4 (medium) Release wheel keeps the legacy `biopipe_` prefix

The published asset is `biopipe_studio-3.0.2-py3-none-any.whl` while every other
artifact is `Operon-*`. Automated consumers that follow the new naming
(`operon_studio-3.0.2-...whl`) will not find it.

Recommended: upload an identically built wheel named
`operon_studio-3.0.2-py3-none-any.whl` next to the legacy asset (same contents,
same checksum), and note the alias in the release body. If assets are frozen,
document the legacy name in the release body and in
`docs/command_line_installation.md`.

### D5 (high, fixed on main) "Operon, formerly Operon"

`docs/README.md:3` at `v3.0.2` reads:

> Operon, formerly Operon, prepares reproducible analysis results ...

The rename replaced the old product name inside the "formerly" clause. Replace
with "Operon, formerly BioPipe". Fixed on `main`; the 3.0.2 bundle still ships
the old sentence.

### D6 (medium, fixed on main) SDK 3.6-only label on a 3.7 release

`docs/README.md:71` labels the format guide as "SDK 3.6 logical types,
representations and conversion plans" although 3.0.2 introduces SDK 3.7.
Change to "SDK 3.6/3.7". Fixed on `main`.

### D7 (medium, fixed on main) Rebranding table says SDK 3.6 only

`docs/rebranding.md:16` says "optional SDK 3.6 format capabilities are
independent of the product name". With 3.0.2 the supported optional capabilities
are 3.6 and 3.7. Fixed on `main`.

### D8 (low) Server bundle has no quickstart and no operator counts

`Operon-3.0.2-Server.zip` ships `docs/` with five pages and no
`QUICKSTART.md`/`QUICKSTART.zh.md` (neither exists at `v3.0.2`). The bundle
README gives a shell example but no five-minute path from install to first
result and no pointer to a library upgrade. Add the bilingual quickstart (as
done for 5.0.0) and one sentence on upgrading the operator library.

## Suggested order of work for the frontend release owner

1. L1 + L2: fix README license section and package metadata.
2. L3 + L4: ship NOTICE/THIRD_PARTY_NOTICES in the server bundle and in the
   Windows installer, and show the license in Setup.
3. L5: attach or correct the pgenlib source offer.
4. D1 + D2: release body/branch statement and the CI link (these can be fixed in
   the GitHub release body without rebuilding).
5. D3 + D4: state the bundled library version; add the `operon_studio` wheel
   alias or document the legacy name.
6. D5-D8: documentation carries into the next build (already fixed on `main`).

Note on immutability: tag assets for `v3.0.2` should not be replaced in place.
Items that require rebuilding should land in the next application release; the
release body and README can be corrected immediately.

## Verification checklist after changes

- [ ] `grep -ri "proprietary\|All rights reserved" README.md docs/` returns no
      license contradiction.
- [ ] `frontend/package.json`, `pyproject.toml`, `library/pyproject.toml` declare
      `Apache-2.0`.
- [ ] `unzip -l Operon-*-Server.zip` lists `LICENSE`, `NOTICE` and
      `THIRD_PARTY_NOTICES/`.
- [ ] Windows install directory contains `LICENSE`, `NOTICE`,
      `THIRD_PARTY_NOTICES/`; Setup shows a license page.
- [ ] pgenlib source archive is present in the assets or the notice is corrected.
- [ ] Release body CI link uses the `Operon` repository path.
- [ ] Release body states the bundled library version and counts.
- [ ] `docs/README.md` has no "formerly Operon".
