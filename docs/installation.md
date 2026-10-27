# Installation and dependency versions

## Bundled Windows runtime

The full desktop packaging recipe supplies a clean, relocatable CPython 3.11 x64
runtime, core Studio/MCP dependencies and the declared CPU dependencies of the
bundled Readers and Steps. Users extract the entire ZIP and double-click the EXE;
they do not need Python, Conda, pip or a compiler. Full packages start with 0.4.0;
0.3.4 and earlier desktop ZIPs require an existing environment.

Full packages set `bundledRuntime: true`. They always select the adjacent
`runtime/python/python.exe` and ignore remembered/PATH/environment interpreter
choices. A missing or damaged bundle produces a diagnostic rather than silently
using another installation. Python starts in isolated mode, excluding user-site
packages and `PYTHONPATH`. The explicit `--select-runtime` maintenance action can
override this choice for one launch.

If WebView2 is absent, the included, signature-verified Microsoft bootstrapper
prepares it for the current user. That one-time step needs internet access.
Already-bundled CPU analyses do not require downloads. New extensions may need
internet access; package availability, OS support and GPU drivers still matter.
Windows x64, macOS, Linux and Windows ARM need separate tested distributions.

### Dependency state

At startup Studio reads declarations from the registry without rescanning source.
Checks run outside the UI process. States are `unchecked`, `checking`, `installing`,
`passed` and `failed`. Successful checks are held in memory until shutdown, not
loaded as trusted results from disk on the next launch. Library installation,
refresh and **Repair dependencies** retry only entries that have not passed.
A changed implementation or changed declaration becomes a new unchecked entry.
Disabled operators are excluded until enabled again.

Compatible operators share one dependency set. A declared version conflict selects
an immutable private dependency directory and an independent subprocess using the
same Python executable. Running jobs retain their frozen paths and descriptors;
existing compatible operators are not moved into child processes. Installation
and import failures remain visible. See [selective dependency isolation](dependency_isolation.md)
for resolution, memory accounting, streaming and limitations.

`dependencies` accepts PEP 508 names, extras, version ranges and markers, but not
machine paths or dependency URLs. `dependency_imports` optionally verifies imports
to catch broken native libraries. Logs are written to `logs/dependencies.jsonl`
inside the resolved Studio data directory, alongside normal run/desktop logs.
The library manager displays the state and provides a retry button.

### Build a full package

From a Windows x64 checkout, obtain a clean standalone interpreter, then build:

```text
uv python install 3.11 --install-dir .local/portable-python --no-bin --no-registry
python scripts/build_runtime.py --python-home .local/portable-python/cpython-<version>-windows-x86_64-none --output .local/runtime/python
powershell -File scripts/build_desktop.ps1
python scripts/package_release.py --runtime .local/runtime/python
```

Replace `<version>` with the exact directory produced by uv. The builder rejects
developer environments and venvs, resolves dependencies using the Windows 3.11
constraints, tests imports and `pip check`, and writes a resolved lock and runtime
receipt. Retain those with each release. The runtime is copied beside the EXE;
no builder path becomes an interpreter setting. `--lite` explicitly builds the
old package for users supplying their own environment. The full build also
downloads the official WebView2 bootstrapper and verifies its Microsoft signature.

The runtime builder creates the SDK wheel from a fresh source distribution so
deleted modules cannot leak in from an old `build/lib` directory. Use
`python -m build --no-isolation` (the default source-then-wheel build) when producing
the separate release wheel, too; check its module list against the source tree.

Before a release changes bundled implementations, record the identities from
checksum-verified prior release extractions:

```text
python scripts/record_bundled_history.py --source <verified-release-folder> --release vX.Y.Z --commit <full-release-commit>
```

This reads code/declaration bytes and checks the source against its index and
package manifest. It does not import the historical operators. The generated
`biopipe/bundled_history.json` contains only compact identity receipts, not old
implementations, profiles or datasets. Commit it and include it in both the SDK
wheel and desktop packages. Never generate trusted receipts from an unverified
user extension or from an edited release folder.

Native dependencies without a compatible Windows wheel must be built and tested
by the release maintainer, not by the recipient. Supply those artifacts with
`build_runtime.py --wheelhouse <directory>`. The release's PLINK 2 wheel is built
from pgenlib 0.95.1 and zlib 1.3.2 with `scripts/build_pgenlib_windows.py`; run that
script in an x64 MSVC developer prompt with clang-cl, NumPy 2.x, Cython >=3.1 and build
installed. It verifies the upstream source hashes, applies the Windows compiler
recipe and retains the modified source archive beside the wheel. Release assets
include this source archive. The recipient does not run this build.
Use `--bundle-wheels <native-wheel-directory>` to retain these compiled wheels in
the runtime for later dependency repair or private targets. `--offline` with a
complete `--wheelhouse` makes the release build resolve without package-index
access; the bundled lock records the exact result.
A failed runtime build never produces a completion receipt or silently omits a
Reader. The dependency manager reports unavailable or incompatible libraries.

Sources: [standalone Python used by uv](https://docs.astral.sh/uv/concepts/python-versions/)
and [Microsoft WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution).

## Source and existing environments

BioPipe publishes supported dependency ranges in `pyproject.toml` and the
`requirements*.txt` files. Release users can select one tested combination with a
constraints file. Both direct and transitive dependencies are pinned with `==`.
The files contain package versions only: no local paths, copied environment,
private index, Conda build path or interpreter location.

Validation: a clean CPython 3.11.15 / Windows x64 installation with the 3.11
constraints passes `pip check` and 73 tests covering contracts, memory management,
Studio, the desktop backend and CLI/MCP agent transports. A core-only install
plan selects 45 packages and excludes pytest and build tooling.

## Windows x64, Python 3.11

Activate a Python 3.11 environment, then run from the extracted package or checkout:

```text
python --version
python -m pip install -c constraints-py311-windows.txt -e ".[agent]"
python -m pip check
```

If only the dependencies are needed for an existing source checkout:

```text
python -m pip install -c constraints-py311-windows.txt -r requirements.txt
```

For development and tests:

```text
python -m pip install -c constraints-py311-windows.txt -e ".[agent,dev]"
```

`requirements-dev.txt` is the equivalent dependency-only entry point. Normal
core Studio installations do not require `pytest`, `build` or `setuptools` at runtime.
A constraints file restricts packages that are requested; it does not install
every listed package. Therefore a `pytest` pin in the constraints does not add
pytest to an ordinary desktop installation.
The full Reader bundle can include testing/build utilities through upstream
dependencies (for example, `cbgen` declares `pytest`); these are already installed
in the complete environment and require no user setup.

## Windows x64, Python 3.12

Use the same commands with `constraints-py312-windows.txt`. Do not substitute the
Python 3.12 file on Python 3.11: some newer scientific packages require 3.12.
The Python 3.12 combination follows the desktop verification environment.

For other operating systems, architectures or Python versions, use the supported
ranges and resolve a suitable environment there; the Windows files are not
cross-platform locks. Optional analyses and native Readers are outside these core
constraints; install their respective `requirements-analysis.txt` and
`requirements-readers.txt`. These optional groups may need a separately resolved
combination rather than forcing the core release constraints onto every plugin.

## Resolver backtracking

`pip is looking at multiple versions ...` means that pip is trying alternative
dependency combinations. That message alone does not identify the conflicting
package. Exact constraints reduce the search space; they do not override an
incompatible Python version or make conflicting requirements compatible.

Use an isolated environment when another project already imposes conflicting
requirements. If an install still fails, keep the command, Python version and
final conflict error. Do not work around unresolved dependencies with `--no-deps`.
See the [pip resolver documentation](https://pip.pypa.io/en/stable/topics/dependency-resolution/).

## Updating the constraints

Resolve each supported target explicitly, verify a clean installation and run the
relevant tests before committing an updated file. For example, with uv available:

```text
uv pip compile pyproject.toml --extra agent --extra dev --python-version 3.11 --python-platform windows --only-binary :all: --no-header --no-annotate --no-sources -c constraints-py311-windows.txt -o constraints-py311-windows.txt
```

This command verifies the existing pins. To upgrade, remove or adjust only the
intended constraints, then resolve and test again. Avoid exporting an entire
developer environment with unrelated packages or local editable URLs.
