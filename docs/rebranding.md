# Operon naming and compatibility

The application is named **Operon** starting with the 3.0.0 candidate. Operon is
the earlier product name. The rename changes the product presentation, not the
meaning of a saved scientific workflow or an installed operator ID.

| Surface | Naming policy |
| --- | --- |
| Windows application, installer and shortcuts | Operon Studio; the distributable installer is `Operon_Setup.exe` and the workspace displays Operon |
| Application version | 3.0.2; independent of the operator-library version |
| Python package and source directories | Existing `operon`, `operon_sdk` and `src` imports remain valid |
| Command-line automation | Existing `operon` / `python -m operon` remain supported; the `operon` command is the branded alias |
| MCP names | Existing `operon_*` tools and resource identifiers remain valid |
| HTTP routes and authentication | Existing application/agent API paths and scopes remain valid |
| Saved formats | `operon.workflow`, parameter/execution sidecars, plugin IDs and implementation pins retain their wire identifiers |
| Operator protocol | Base major 3; existing v3/v3.5 packages remain accepted; optional SDK 3.6 and 3.7 format capabilities are independent of the product name |
| Previous evidence and documentation | Historical release names, filenames, URLs and log records retain their original spelling |

Do not rename a plugin ID, Python import or JSON discriminator merely to make it
look branded. A public identifier is an interoperability contract. The product
name in a window is display text.

## Installation and old data

Setup creates a new software installation and a fresh isolated profile, then uses
its adjacent bundled Python. It must not redirect an existing Operon installation
to the new interpreter, rewrite its global runtime hint or silently migrate its
old plugin registry. Import saved workflows explicitly into the new workspace.
Old user profiles and analysis outputs remain available.

New Setup receipts declare `product: "operon"`; their profiles live under
`%USERPROFILE%\.operon\profiles\<installation-id>`. Receipts from older Operon
installations without this marker retain their original `.operon/profiles`
resolution. This compatibility rule does not copy old state into the fresh Operon
profile. Read the actual receipt rather than constructing the random ID yourself.

Locate the current executable, profile, workspace and logs from the current
installation receipt and desktop startup log. Do not assume that replacing the
word `Operon` in an old filesystem path identifies the new location. Internal
compatibility filenames can retain that spelling. No test or script should embed
a developer's home directory or machine-specific installation path.

The application and scientific library remain separate distributions. A branding
change does not require changing every scientific provider or reinstalling an
unrelated user's environments. Standard v3 library installation, refresh and
dependency preparation retain their existing responsibilities.

## Acceptance boundary

The [3.0 acceptance guide](OPERON_3_TEST_ACCEPTANCE.md) checks actual Setup and
shortcut launches, preserved Operon state, version/title visibility, legacy
automation, new authoring features and uninstall behavior. A passing source test
or a renamed executable alone is not evidence that the installer passed.

The 3.0 candidate does not claim a universal standalone scientific exporter,
automatic provisioning for every script dependency, or Windows verification of
Linux-only tools. See [implementation scope](V3_IMPLEMENTATION.md) before writing
release notes.
