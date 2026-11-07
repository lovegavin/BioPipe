# Languages and operator library management

## Studio architecture

Studio is a React + TypeScript application built with Vite. React Flow renders
the workflow canvas. The Windows desktop host displays the same assets and calls
the same Python/FastAPI service as the browser interface.

`frontend/src/i18n/zh-CN.json` and `en.json` contain UI messages. `t(message, values)`
resolves a message at render time and interpolates named placeholders. The Chinese
source message is its stable lookup key; English is a separate dictionary, not a
second component tree. A small external store broadcasts language changes without
remounting the editor or settings forms. `useLocale()` subscribes memoized views.
Dates use the selected locale. Logs, backend diagnostics, user names, file paths
and scientific data remain verbatim.

Settings → Language offers Simplified Chinese, English and the system setting.
Language, appearance, default viewers and configured viewer paths share the current
profile's `.studio/config.json`. Settings updates merge only their own fields under
one file lock and write atomically. The browser caches language and theme together
for the first paint; changing the desktop loopback port does not lose preferences.
Existing browser-only appearance is imported only when the profile has no saved
choice. Earlier viewer settings are imported once without deleting the originals.
It is not a workflow parameter. Unsupported system languages use English. To add another UI
language, add a dictionary, register its locale in `i18n/index.ts`, and add a choice
in `LanguageSettings.tsx`. Every dictionary must have the same interpolation tokens.
Translate at render time, never use translated strings as IDs or enum values.

Example application configuration:

```json
{
  "language": "en",
  "theme": "dark",
  "viewers": {
    "paths": {},
    "defaults": {".hic": "juicebox"}
  }
}
```

Server connection profiles and credentials remain in their existing connection
stores. Workflow-specific execution budgets and frozen operator parameter values
remain independent of this application configuration. The settings pages do not
create a separate preference file for each panel.

## Library navigation

The existing footer entry opens **Manage library**. It contains package status,
refresh, dependency repair and enable/disable/remove controls. The large **+**
opens **Add operators** in the same window:

* Import an individual `.whl` or a complete `.operon-library.zip`.
* Open operator/Reader source directories and scan for added or edited files.
* Select one or more saved workflows and register them as workflow operators.
* Import workflow JSON or a `.operon.zip` bundle, save it and register it.

Changing pages preserves selection and search. Importing here does not replace
the active canvas or submit a run. Successfully saved imports remain available
if a later file fails. Runtime errors are shown and the current library remains
managed by the existing transactional backend. The server-library entry continues
to open server settings; this window manages the local library.

Saving an incomplete canvas creates an editable draft; it does not make that
canvas a runnable workflow operator. Registration validates the internal graph.
For example, a PCA node needs a source connected to its input before registration.
Input file contents need not be present on the registration computer. Failures
remain visible outside the scrolling library content, retain the selection, and
leave the previous registry unchanged. Connect the missing ports, save the route
again, and retry **Add to library**.

## Operator protocol v3.5

This is an additive presentation revision of protocol v3. The wire field remains
`"protocol_version": 3`; the compiler adds `"protocol_revision": "3.5"` when a
language pack is declared. **SDK 3.5 accepts existing v3 packages unchanged.**
Older SDKs are not expected to accept new v3.5 descriptors; upgrade the host/server
before installing a language-enabled package.

An authoring unit can contain four adjacent files:

```text
scale.py                 # literal definition and implementation
scale.parameters.json    # parameter schema and defaults
scale.md                 # operator documentation
scale.i18n.json           # optional translated display text
```

Declare the sidecar on either an Operator/Step or a Reader:

```python
class Scale(Operator):
    parameters_file = "scale.parameters.json"
    localization_file = "scale.i18n.json"
    definition = {
        "protocol_version": 3,
        # ... existing identity, contracts and resource declaration ...
    }
```

Example language pack (the `method` field must exist in the parameter schema):

```json
{
  "default_locale": "en",
  "translations": {
    "en": {
      "title": "Scale matrix",
      "description": "Scale values while retaining axis metadata.",
      "parameters": {
        "method": {
          "title": "Method",
          "description": "Choose the calculation method.",
          "enum_labels": {"\"fast\"": "Fast"}
        }
      }
    },
    "zh-CN": {
      "title": "矩阵缩放",
      "parameters": {
        "method": {"title": "方法", "enum_labels": {"\"fast\"": "快速"}}
      }
    }
  }
}
```

Enum label keys are **JSON-encoded values**: `"\"fast\""` refers to the string
`fast`, while `"1"` refers to the number 1. Labels do not change the selected value.
Only `title`, `description`, and per-parameter `title`, `description`, `enum_labels`
are allowed. Unknown parameters, unknown enum values, duplicate locale tags,
malformed language tags and undeclared fields fail validation. Defaults, IDs,
dependencies, contracts and memory capabilities belong in their original files.

Fallback applies **per field**: requested locale → base language → declared default
locale → original declaration. A v3 operator without a language pack displays its
original text. Custom user node titles and saved route names remain unchanged.

## Packaging, refresh and identity

Include `*.json` in setuptools package data (nested sidecars need matching patterns).
The standard `operon plugin init` templates already include a language pack and
package-data rules. The source-folder scanner also copies declared language files.
No translation service or additional Python environment is needed.

The compiler reads the AST and JSON without importing implementation code. It
stores validated translations plus their relative path and content hash in the
registry. Startup reads this index; it does not rescan every sidecar. Installation
checks wheel bytes against that index. Paths must stay inside the module directory.

Rebuild/refresh after editing the sidecar. Translation-only changes update the
declaration hash and UI. They preserve code and execution digests, so compatible
metadata updates reuse installed dependency targets and existing workflow pins.
Frozen workflow parameter JSON remains authoritative. A first-time code edit to add
`localization_file` legitimately changes code identity; subsequent sidecar edits do not.

Use `operon_sdk.localization.project(descriptor, locale)` for a display-only Python
projection. Never write that projection over the canonical descriptor or job lock.
CLI/MCP compact discovery stays in the declaration's original language to avoid
inflating agent responses with every translation.

## Try the complete example

`examples/localized_operator/` contains a runnable v3.5 operator with independent
parameter and language JSON. Copy its files into the local operator directory and
click **Add operators → Scan for operators**, or build a wheel with the standard
plugin tooling. Its `scale_factor` value stays unchanged when the UI language changes.

Verification includes static discovery with forbidden top-level execution, corrupt
and missing sidecars, v3 fallback, Reader scaffolds, UI projection purity, package
refresh without dependency reinstallation, and importing an old workflow into a
fresh profile using its frozen values after a translation update.
