# Independent operator library releases

BioPipe Studio and the operator library are **separate release products**. Adding
or fixing compatible operators and Readers does not require rebuilding Lite,
Full, the desktop host, the frontend, or the application wheel. Protocol v3,
independent workflow parameter JSON and the existing memory/streaming runtime
remain unchanged.

| Product | Version/tag | Distribution | Installation |
| --- | --- | --- | --- |
| Studio application | `v2.0.4`, then application SemVer | Lite, Full, application wheel | Upgrade application |
| Operator library | `library-v2026.11.4`, then independent calendar version | `.biopipe-library.zip` | Library manager **Import package**, or CLI |
| One provider | provider version | `.whl` | Same library manager |
| Saved route | route's own revision | saved route and frozen parameter JSON | Import route |

`main` is a source branch, not an instruction to replace installed software.
The library release branch/tag identifies the exact library sources used; the
builder reads only the operator/Reader trees and provider index. Engine and
frontend files from that branch are never installed by a library update. A
desktop ZIP may include an initial library for offline startup, but that seed
does not overwrite an independently installed profile library.

## For users

Download the **Windows** or **Linux** `.biopipe-library.zip` matching the host from a **BioPipe Operator Library** release. The v2.0.4 installer uses native wheel archive comparison, so separate envelopes are required although their library source is the same.
In Studio open **算子库管理 → 导入包 (Import package)** and select the ZIP. The
installation publishes a new registry generation and the canvas can use the
new entries without replacing or restarting the EXE. The equivalent command is:

```bash
biopipe plugin install ./BioPipe-Library-v2026.11.4-Windows.biopipe-library.zip
```

Use the profile used by Studio. **Refresh** scans the editable local source
directories; it does not fetch GitHub updates. Import is the explicit update
action. Automatic network update discovery is not part of this release.

Checksums, protocol and minimum application version are checked before
publication. Failed imports leave the active registry intact; disabled packages
remain disabled. The same ZIP can be imported again without changing generation.
Saved workflows retain frozen values and pins; historical jobs keep their old
generation. Unrefreshed local edits must first be refreshed or exported.

Python dependency declarations use the existing dependency manager, including
conflict isolation. Optional system tools and large biological databases still
require their declared platforms/resources; installing an adapter does not
install a database or make a Linux tool run natively on Windows.

## For library maintainers

1. Write v3 code, adjacent parameter JSON and Markdown. Update the static indexes
   with `python -m biopipe registry build` and `python scripts/build_operator_docs.py`.
2. Change only the library version in `library/release.json` and `library/pyproject.toml` (calendar
   `YYYY.M.D`, optional `.N` for another release that day). Do not bump
   `pyproject.toml`, `biopipe/__init__.py` or the desktop version for operator-only
   changes. Individual operator/provider versions still express their contracts.
3. Set `minimum_application` to the oldest **actually tested** released engine.
   `build_application` must equal it. A new SDK/runtime feature may require a
   newer application; changing an operator alone does not.
4. In a separate environment install that released application wheel, then:

   ```bash
   python -I scripts/release_library.py --output build/library --tag library-v2026.11.4
   python -I scripts/verify_library_release.py --bundle build/library/BioPipe-Library-v2026.11.4-Windows.biopipe-library.zip --work build/library-verify
   ```

   Do not use `pip install -e .` in this environment. `-I` excludes checkout/user
   imports. The builder deliberately rejects a different or editable engine.
5. Add `docs/releases/library-v<VERSION>.md` with additions, compatibility and
   scientific validation limits. Commit on the library release branch, test it,
   then push the matching annotated `library-v<VERSION>` tag. Never move a tag.
6. **Independent operator library** CI installs the released engine, builds and
   tests on Windows and Linux, then publishes only the library ZIP, checksum and
   verification report. It never builds an EXE or makes a library the GitHub
   "Latest" software release. Both platform jobs must pass before publication.

The verification script checks a complete install on the older engine, unchanged
application files, disabled providers, no-op repeated import, historical pins,
frozen parameter values, resource lookup from the installed provider and a real
streaming worker. The seven new external-tool adapters also run their parser,
synthetic-process and error tests. Real external-tool/database validation is a
separate scientific gate; the automated adapter suite does not claim it.

## Library-owned resources

`library/seed/src/task/step/steps/resources.json` travels beside `_resources_common.py` in
every provider wheel. Resource lookup uses that immutable provider's directory,
not the application's manifest or working directory. Adding a database entry
therefore does not require updating Studio. Defaults use portable home-relative
locations; operator parameters and documented environment variables can point
at existing installations. Database/model contents are not bundled.

This remains the existing v3 library envelope and installer, not a new protocol.
