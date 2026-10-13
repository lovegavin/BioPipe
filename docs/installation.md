# Installation and dependency versions

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
Studio installations do not require `pytest`, `build` or `setuptools` at runtime.
A constraints file restricts packages that are requested; it does not install
every listed package. Therefore a `pytest` pin in the constraints does not add
pytest to an ordinary desktop installation.

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
