# Operon 5.0.0 license audit

Date: 2026-11-07
Scope: repository `/home/gavin/Operon` (release/5.0, tag `library-v5.0.0`), Studio 3.0.2
installer inputs, and the published Library 5.0.0 assets.

## Verdict

The **root `LICENSE` is the Apache License 2.0** and `NOTICE` already declares
Apache-2.0. The project is *not* consistently presented as Apache-2.0 yet:

1. **`README.md` §License contradicts the license file.** Lines 1109-1113 say
   "All rights reserved. This software is proprietary ... prior written
   permission", which cannot coexist with an Apache-2.0 `LICENSE`.
2. **Package metadata has no license field**: root `pyproject.toml`,
   `library/pyproject.toml`, `frontend/package.json` and the desktop/installer
   projects do not declare `Apache-2.0`, so `pip show`, npm and the installer UI
   cannot surface it.
3. **LGPL-3.0 pgenlib notice is not backed by an artifact.**
   `THIRD_PARTY_NOTICES/PGENLIB-WINDOWS.md` says the Windows x64 runtime ships
   pgenlib 0.95.1 and that release assets include the modified source archive.
   `build/release-5.0.0/` contains **no pgenlib source archive**, and the release
   note does not mention one. LGPL-3.0 requires the corresponding source to be
   available with the binary distribution.
4. The **installed application** does not display a license page: the installer
   project has no `LicenseFile` entry, and the About dialog has no license or
   NOTICE link (checked desktop/installer sources).

Because the README is published with the frontend/Studio release and the
frontend sources are owned outside this backend workspace, the exact edits are
listed here as suggestions instead of being applied silently.

## Inventory

Tracked license/notice files (10):

| File | Size (B) | Content |
| --- | ---: | --- |
| `LICENSE` | 11,358 | Apache License 2.0, full text |
| `NOTICE` | 615 | Operon, Copyright 2026 Haojian Li, Apache-2.0 |
| `THIRD_PARTY_NOTICES/frontend-licenses.txt` | 139,792 | 30 bundled npm packages (React 19.3, d3, xyflow, ...) |
| `THIRD_PARTY_NOTICES/PGENLIB-WINDOWS.md` | 1,481 | pgenlib 0.95.1, LGPL-3.0-only |
| `THIRD_PARTY_NOTICES/microsoft.netcore.app.runtime.win-x64-8.0.27-LICENSE.TXT.txt` | 1,139 | .NET runtime license |
| `THIRD_PARTY_NOTICES/microsoft.netcore.app.runtime.win-x64-8.0.27-THIRD-PARTY-NOTICES.TXT.txt` | 68,910 | .NET third-party notices |
| `THIRD_PARTY_NOTICES/microsoft.web.webview2-1.0.4258.31-LICENSE.txt.txt` | 1,487 | WebView2 license |
| `THIRD_PARTY_NOTICES/microsoft.web.webview2-1.0.4258.31-NOTICE.txt.txt` | 3,894 | WebView2 notice |
| `THIRD_PARTY_NOTICES/microsoft.windowsdesktop.app.runtime.win-x64-8.0.27-LICENSE.txt` | 1,137 | WindowsDesktop runtime license |
| `frontend/public/font-licenses/geist-OFL.txt` | 4,486 | Geist font, SIL OFL 1.1 |

Total 234,299 B. `frontend-licenses.txt` bundles 30 dependency entries; the
Geist font is additionally shipped under `frontend/public/font-licenses/`.

## Required changes

### A. Frontend/Studio (README ships with the frontend release)

1. Replace `README.md` §License (lines 1109-1114) with:

   ```markdown
   ## License

   Copyright 2026 Haojian Li.

   Operon is licensed under the Apache License, Version 2.0. You may obtain a
   copy of the License at <https://www.apache.org/licenses/LICENSE-2.0>.

   The distribution also includes third-party components under their own
   licenses; see `NOTICE` and `THIRD_PARTY_NOTICES/` (including the LGPL-3.0
   pgenlib runtime and its source offer).
   ```

   Remove the "proprietary / commercial licensing" paragraph and the contact
   block, or move it to a non-license "Commercial support" section that does not
   restrict the Apache-2.0 grant.
2. `frontend/package.json`: add `"license": "Apache-2.0"`.
3. Ensure the bundled frontend contains `LICENSE`, `NOTICE` and
   `THIRD_PARTY_NOTICES/` (Vite build copies only `public/`; ship these files
   alongside the installer or inside the app resources).
4. Add a "Third-party components" subsection to README that points at
   `THIRD_PARTY_NOTICES/` and states the LGPL-3.0 source offer for pgenlib.

### B. Backend/library (can be applied in this repository)

1. Root `pyproject.toml` and `library/pyproject.toml`:

   ```toml
   license = { text = "Apache-2.0" }
   ```

   and, for setuptools, include the files in the sdist/wheel:

   ```toml
   [tool.setuptools]
   license-files = ["LICENSE", "NOTICE"]
   ```

2. Add `LICENSE`/`NOTICE` to the wheel `*.dist-info` (verify with
   `python -m zipfile -l dist/*.whl | grep -i license`).
3. Add a `License` section to `docs/releases/library-v5.0.0.md` stating
   Apache-2.0 and linking the repository `LICENSE`.

### C. Installer / desktop

1. Add an Inno Setup `LicenseFile=..\LICENSE` page (or show the Apache-2.0 text
   before install).
2. Ship `NOTICE` and `THIRD_PARTY_NOTICES/` next to the installed runtime and
   expose them from the About dialog.
3. Publish the pgenlib 0.95.1 modified source archive as a release asset
   (`pgenlib-0.95.1-operon-src.zip` or equivalent) and link it from the release
   notes and `THIRD_PARTY_NOTICES/PGENLIB-WINDOWS.md`; otherwise remove the
   claim and stop shipping the LGPL runtime.

## Third-party obligations

| Component | License | Obligation |
| --- | --- | --- |
| pgenlib 0.95.1 (Windows runtime) | LGPL-3.0-only | Provide corresponding source + notices; allow relinking |
| .NET 8 / WindowsDesktop runtime | Microsoft EULA + third-party notices | Ship the two Microsoft notice files |
| WebView2 1.0.4258.31 | Microsoft terms + notice | Ship license + notice |
| Geist font | SIL OFL 1.1 | Ship OFL text; do not sell the font standalone |
| 30 npm bundles (React, d3, xyflow, ...) | MIT/ISC/Apache-2.0 etc. | Ship `frontend-licenses.txt` |

## Verification checklist

- [ ] `README.md` has no "proprietary"/"All rights reserved" text.
- [ ] `pip show operon-studio` and `pip show operon-builtin-library` report
      `License: Apache-2.0`.
- [ ] Built wheels contain `LICENSE` and `NOTICE` in `.dist-info`.
- [ ] `frontend/package.json` reports `Apache-2.0`.
- [ ] Installer shows the license page and About links to `NOTICE`.
- [ ] Windows release assets include `pgenlib` source archive and the release
      note links it.
