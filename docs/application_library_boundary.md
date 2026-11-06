# Application and operator library

BioPipe has two versioned products in one repository. Application releases use
`vX.Y.Z`; operator releases use `library-vYYYY.M.D`. Adding or correcting an
operator does not require an EXE release or an application version change.

| Owner | Source | Published artifact |
| --- | --- | --- |
| Application, engine, CLI, HTTP, MCP, desktop | `biopipe/`, `biopipe_sdk/`, `src/core/`, `src/task/`, `src/web/`, `frontend/`, `desktop/` | `biopipe_studio` wheel, Lite and Full desktop archives |
| Reference operators and Readers | `library/seed/src/task/step/steps/`, `library/seed/src/reader/readers/` | Independent native `.biopipe-library.zip` bundles |
| Factory metadata and templates | `library/seed/biopipe/`, `library/seed/src/web/`, `library/seed/routes/` | `biopipe_builtin_library` seed wheel |

The application wheel contains no analysis implementations, parameter sidecars,
operator index or factory route graphs. Without a seed it starts with an empty
library, and can install provider bundles. The two old implementation namespaces
contain only lazy location bridges. V3 entry-point strings and source paths inside
the library remain stable; moving the files does not itself change their hashes.

## Installation and updates

For source development:

```sh
python -m pip install -e '.[agent,dev]' -e ./library
python -m biopipe registry check
```

For a standalone installation, install the application wheel and optionally the
separately versioned seed wheel. Neither wheel requires the other to be rebuilt.
Lite and Full archives include `library/seed/` as an explicit offline seed so a
new user sees the reference library immediately. The seed is not part of the EXE
or application wheel. User profiles keep their independent provider generations,
disabled states and editable copies; an application update does not overwrite
an explicitly installed library.

To publish operator changes, edit the library sources, adjacent parameter JSON
and Markdown, run `biopipe registry build` and `scripts/build_operator_docs.py`,
then update `library/release.json` and `library/pyproject.toml`. Use the existing
library build/verification commands in [Library releases](library_releases.md).
The native bundle can be installed through Studio's library manager or the CLI.
The seed wheel is for administrators building a new installation or updating its
factory templates/isolated-environment recipes. It does not replace profile-owned
provider versions.

An unchanged refresh compares the editable factory copy with its installed seed
and reuses the compiled registry. It does not rebuild provider wheels, reinstall
them, precompile them again, or change workflow pins. Byte comparisons include
parameter JSON and documentation, so an edit made before the first refresh is
not missed. Once editable sources change, refresh uses the existing transactional
snapshot/install path and detaches those providers from the factory library.
Explicitly installed library bundles remain independently versioned as before.

## Compatibility

Protocol v3 is unchanged. Workflows keep their independent frozen parameter JSON;
defaults in a later library are never substituted into a saved graph. Existing
operator IDs, ownership and pin resolution are retained. Jobs retain their locks
and output paths. Streaming, disk Readers, memory admission and emergency spill
continue through the same engine interfaces.

## Server deployment

Automatic deployment installs the base application, the separate reference seed
and the declared Hi-C toolchain. It does not eagerly install every model package
in the operator library. The base environment is validated with `pip check` and
real native-tool commands. Missing optional library capabilities retain failed
states and actionable errors in the installation receipt and handshake.

A passed receipt is reused only for a matching implementation, dependency
declaration and runtime. It cannot overwrite a fresh failed check. A workflow
requiring an unavailable capability remains blocked until that capability is
repaired. A tool name alone is not an installation recipe; arbitrary third-party
executables still need their documented installation procedure.

Setup logs are under the selected server directory:
`<managed_root>/managed-v1/setup-<source-id>.log`. The desktop displays the exact
path before upload. Log output is appended on retries and includes extraction
and installer failures. Reconnecting to a registered server reads its installation
document; it does not upload or reinstall the application.
