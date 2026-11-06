# Windows Setup and isolated installations

Download **Operon_Setup.exe** and double-click it. The installer contains the
Windows application, a tested Python runtime and the reference library seed.
There is no Python selector or Lite/Full decision. Setup installs for the current
Windows user and creates desktop and Start menu shortcuts.

The default 3.0 candidate includes a **management runtime**, not a complete
scientific environment. It contains HTTP/MCP/SSH management dependencies and
NumPy for Form, the memory store and bounded previews. It excludes PyTorch,
Pandas, SciPy, Statsmodels, Matplotlib and specialized analysis packages.
Operator manifests, code and documentation remain available without those packages.

Choose local or SSH execution in the application. Validate checks only the route
on the selected host. If blocked, explicitly prepare that route's dependencies;
local packages go into profile-owned immutable dependency directories, and remote
packages stay on the server. Run itself never grants installation permission.
The first analysis preparation requires internet access. Local workers reuse the
bundled Python executable with separate dependency paths; the management runtime
is not modified. Arbitrary local Python selection and a custom dependency-storage
directory UI remain later work, not capabilities of this candidate.

## A clean environment on every installation

Each run creates a fresh software directory and a fresh profile identity. The
installed application always selects its adjacent Python. It does not fall back
to Conda, system Python, remembered interpreters or a previous installation.
Startup does not create or update the shared `~/.biopipe/runtime.json` hint.
That file remains available to portable/development installations; uninstalling
Setup cannot leave them pointing at the removed bundled Python.
Inherited Python, Conda and BioPipe overrides are removed from child processes.
The tool search path contains the bundled runtime and Windows system directories.
Optional dependencies use managed targets inside this installation's profile;
conflicting requirements continue to use separate subprocesses.

The new Operon profile is `%USERPROFILE%\.operon\profiles\<installation-id>`.
The random ID is recorded in `biopipe-install.json` beside the installed EXE.
New receipts include `product: "operon"`. Older BioPipe receipts without this
marker retain their `.biopipe/profiles` behavior; the new installer does not
rename or migrate those profiles. See [naming compatibility](rebranding.md).
No machine-specific path is embedded in the distributed installer. Moving the
software folder on the same account retains its profile identity.

**Reinstalling starts a new empty workspace.** Previous workflows, input files,
results, credentials, dependency targets and custom providers are not copied into
the new profile automatically. Old profiles remain on disk. Import saved workflows
or workflow bundles explicitly, and install compatible v3 providers through the
library manager. Unsupported v1 custom providers need conversion before import;
they cannot prevent the new application from starting.

This is dependency and state isolation, not an operating-system security sandbox.
Operators still run with the current user's permissions.

## Old software and recovery

Setup verifies the payload, extracts a new version and checks its bundled runtime
before switching shortcuts. Previously managed software is cleaned using its
installation manifest. Changed or unknown files are retained. Locked files or
incomplete cleanup do not become part of the new runtime. Portable archives and
manually copied directories without an ownership receipt are not deleted by
guessing their names or scanning drives.

On installation failure the previous receipt and shortcuts remain in place. The
new staging directory is removed only after ownership verification. No profile
migration or old registry rewrite is required for installation.

Setup logs and its inspection report are under
`%LOCALAPPDATA%\Operon\Setup\<timestamp-id>`. Choose **View installation log**
in the installer. The receipt records the active EXE and profile; previous profiles
remain independently accessible under their original profile roots.
If LocalAppData is not writable, Setup uses `%TEMP%\OperonSetup` for its logs
and payload cache instead. The report and installer log link show the actual path.
The Python inspection returns its JSON report through stdout; the native installer
saves `inspection.json` in its own log directory. The child does not need write
access there. Dependency-check progress is written to `setup.log` as it happens;
a stalled inspection also emits Python stacks after 30 seconds. Profile JSON
writes retry only actual temporary-name collisions. A permissions failure is
reported immediately and leaves the previous JSON file unchanged.
Desktop logs are in the installation's profile under `logs/`. If another program
locks the daily log against writes, the host uses
`desktop-YYYYMMDD-<process-id>.fallback.log` there. An unavailable log directory
does not interrupt startup, backend output handling or shutdown.

Use Windows **Installed apps > Operon Studio > Uninstall** to remove managed
software. Uninstall preserves profiles, analysis data and unexpected files.

## Connectivity and scope

The core runtime is bundled. First-time WebView2 installation, additional
dependencies, model weights and remote deployment can still require internet.
Proprietary viewers and licenses are not included. Library updates remain
independent of application releases; adding an operator does not require Setup.

## Building and acceptance

The desktop and installer share the embedded icon in `assets/branding/biopipe.ico`.
Its editable SVG, generated PNG and rebuilding instructions are in that directory.
Normal builds use the committed icon and need no extra graphics libraries.

Build the application runtime with `scripts/build_runtime.py --mode management`
(the default), then a Python-bundled payload with `scripts/build_desktop.ps1` and
`scripts/package_release.py --runtime ...`. Then run:

```powershell
python scripts/build_setup.py --payload <full-release.zip> --output <output>/Operon_Setup.exe --build-dir <temporary-build-directory>
```

The build verifies every payload file, embeds its checksum and appends the archive
to the self-contained native installer. Distribute the single EXE and checksum.
Do not replace assets belonging to an already published release.

Acceptance must include actual double-click installation, app startup and exit,
an existing corrupt/legacy default profile, inherited Python/BioPipe overrides,
reinstallation with old software leftovers, and uninstall with a saved workflow.
Verify the interpreter and profile in desktop logs. Command-line smoke tests
supplement actual desktop acceptance.
Check the existence and SHA256 of the global runtime hint before installation,
after startup/restart, and after uninstall. Test both an absent and an existing
hint in isolated test homes. Hold the daily log open without write sharing while
closing the app, and confirm that shutdown completes and a fallback log exists.
Report retained files separately: changed or unknown compiled caches are subject
to the same conservative cleanup policy as other unexpected files.

Automation supports `--quiet --install-dir <directory> --result <report.json>`.
`--no-register` suppresses shortcuts and Windows uninstall registration for tests.
`--uninstall` removes the specified managed installation. Do not target an ordinary
user's installation or profile in automated tests.
