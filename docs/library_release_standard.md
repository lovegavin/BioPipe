# Operator library release standard

This page records the release contract used by the independent operator-library
channel, confirmed against **BioPipe Operator Library 2026.11.5.2** (tag
`library-v2026.11.5.2`, commit `4cc3ad34`). It describes what a library release
must contain and what CI verifies; it does not change protocol v3 or workflow
parameter JSON.

## 1. Scope and independence

- The operator library ships Operators, Readers, route templates, parameter
  schemas, adjacent Markdown and resource declarations.
- A library update does not require a new Studio EXE or a new application version
  unless it uses a new runtime API.
- The application and the library keep separate versions, branches, tags and
  release assets. Application releases use `vX.Y.Z`; library releases use
  `library-v<library-version>`.
- Protocol v3, saved workflow parameters, memory planning, streaming/spill and
  provider-owned state remain frozen.

## 2. Version metadata

`library/release.json` is the single source of truth:

```json
{
  "version": "2026.11.5.2",
  "minimum_application": "2.0.4",
  "build_application": "2.0.4"
}
```

Rules enforced by `scripts/release_library.py`:

- `version`, `minimum_application` and `build_application` are canonical versions.
- `minimum_application == build_application`; the pair names the oldest
  **actually tested** application. The library version is independent and may be
  newer than the host application.
- The annotated tag is exactly `library-v<version>`; any other tag is rejected.
- The release commit updates `library/release.json` and `library/pyproject.toml`
  to the same version.
- `docs/releases/library-v<version>.md` is the GitHub release body.

Calendar versions (`YYYY.M.D[.N]`) are the normal independent-library scheme.
A coordinated semver library release (for example `library-v3.0.0`) uses the same
mechanics but may set both application fields to the coordinated application
version.

## 3. Branch and commit preconditions

- Release from `main`, `library/**` or the independent-library maintenance
  branch.
- The working tree is clean; `tests/test_library_release.py` passes.
- The seed registry, operator index, reader index and adjacent docs are rebuilt
  and committed before tagging.
- No operator, Reader, provider package, route or parameter schema is removed or
  renamed without a library version change.
- Credentials, runtime jobs, private data, model weights and platform binaries
  are never committed.

## 4. Build and verification (must pass before publish)

CI uses two runners, Windows and Ubuntu, Python 3.11. Each runner:

1. Installs the **released application wheel** matching `build_application`
   (`biopipe_studio-<version>-py3-none-any.whl`) plus analysis/test dependencies
   (`pytest`, `h5py`, `scikit-learn`, `biopython`, `rdkit`, CPU `torch`).
2. Runs `python -I -m pytest tests/test_library_release.py -q`.
3. Builds with `python -I scripts/release_library.py --tag library-v<version>
   --output build/library`. The builder rejects a source-checkout import and
   requires `python -I`; it verifies the installed application version.
4. Runs `scripts/verify_library_release.py --bundle <bundle> --work
   build/library-verify`: imports the bundle into a fresh library home, checks
   frozen routes and executes a worker end to end.
5. On Linux, builds the portable seed wheel with `python -m build --wheel
   --outdir build/library library` and writes `SHA256SUMS-seed.txt`.

The builder produces a native envelope per platform
(`BioPipe-Library-v<version>-<Windows|Linux>.biopipe-library.zip`), a
`library-build.json`, a platform `SHA256SUMS-<system>.txt` and a
`verification-<os>.json`.

## 5. Publish

The tag job runs only for `refs/tags/library-v*` and requires the verify matrix:

```bash
gh release create "$GITHUB_REF_NAME" --verify-tag --latest=false \
  --title "BioPipe Operator Library v${GITHUB_REF_NAME#library-v}" \
  --notes-file "docs/releases/${GITHUB_REF_NAME}.md" \
  artifacts/*.biopipe-library.zip artifacts/*.whl artifacts/SHA256SUMS.txt \
  artifacts/verification-*.json
```

`--latest=false` keeps the newest **software** release as GitHub's latest; a
library update must not replace it. Release notes state the base application,
the supported minimum, changed operators/Readers, dependency changes and limits.

## 6. Artifacts and installation

Expected release assets:

- `BioPipe-Library-v<version>-Windows.biopipe-library.zip`
- `BioPipe-Library-v<version>-Linux.biopipe-library.zip`
- `biopipe_builtin_library-<version>-py3-none-any.whl`
- `SHA256SUMS.txt` (all platform sums merged by the publish job)
- `verification-windows-latest.json`, `verification-ubuntu-latest.json`

Windows and Linux users import the native bundle for their host in Library
Management. The seed wheel is for new deployments. An imported provider keeps
its own state; application updates do not overwrite user-installed providers.

## 7. 2026.11.5.2 specifics

- Base application: 2.0.4 minimum; the optional specialist-viewer UI shipped
  separately in Studio 2.4.0.
- `export_results` gained HIC/Cooler, annotated GenBank, BED/bedGraph, GraphML
  and Newick conversion; native-file reuse and branch export are retained.
- HIC/Cooler export validates raw contact counts, chromosome sizes, bin
  coordinates and resolution, and writes bounded batches; balanced/log/OE values
  are not reverse-converted to raw counts. `hictkpy` is an export dependency.
- The GenBank Reader can retain original records for annotation-preserving
  export; sequence-only exports do not invent annotations.
- Genome-track, network and tree exports validate domain metadata; generic
  tensors are not advertised as convertible to arbitrary native formats.

## 8. Release checklist

```bash
# 1. Version and note
#    library/release.json + library/pyproject.toml -> X
#    docs/releases/library-vX.md

# 2. Rebuild generated metadata
python scripts/build_operator_docs.py
python -m biopipe registry build
python -m biopipe registry check

# 3. Release rules (released application must be importable with python -I)
python -I -m pytest tests/test_library_release.py -q

# 4. Build and verify
python -I scripts/release_library.py --tag library-vX --output build/library
python -I scripts/verify_library_release.py --bundle build/library/BioPipe-Library-vX-<OS>.biopipe-library.zip --work build/library-verify

# 5. Commit, annotated tag, push
git commit -m "release: BioPipe Operator Library vX"
git tag -a library-vX -m "BioPipe Operator Library vX"
git push origin main library-vX
```

A tag that has never produced a published release artifact may be corrected (for
example when the first CI run fails before publish). Once a GitHub release
exists, the tag is immutable: never move or reuse it; publish a new patch
version instead.
