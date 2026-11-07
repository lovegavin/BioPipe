# Command-line installation

Installation does not require a desktop window. Windows Setup installs the desktop
application; the Linux installer installs the CLI/API/MCP server. Both keep old
analysis data, install into an isolated runtime, report the actual destination,
and prepare scientific dependencies only when explicitly requested for a route.

## Windows

Download `Operon_Setup.exe`. `--help` lists the supported options without installing.
Use PowerShell's `Start-Process -Wait` so a GUI-subsystem executable is waited for:

```powershell
$target = Join-Path $env:LOCALAPPDATA 'Programs\Operon Studio'
$report = Join-Path $PWD 'operon-install.json'
$arguments = @('--quiet', '--install-dir', ('"{0}"' -f $target),
               '--result', ('"{0}"' -f $report))
$process = Start-Process -FilePath (Resolve-Path '.\Operon_Setup.exe') `
    -ArgumentList $arguments -NoNewWindow -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Setup failed; see $report" }
$installed = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$installed.installDir
$installed.executable
$installed.log
```

`--cli` is an alias for `--quiet`. Progress goes to stderr; the final JSON result
goes to stdout and optionally `--result`. No Studio window is opened automatically.
Exit codes are 0 for success, 1 for installation failure/cancellation, and 2 for
invalid arguments. `--no-register` omits shortcuts and Windows registration, which
is useful for isolated automation. `--payload ZIP` accepts only the exact payload
checksum embedded in that Setup; it is not a way to run an arbitrary archive.

The graphical installer and CLI share destination resolution. A new or empty
directory is used directly. An existing managed Operon directory is reinstalled
in place using a new version/profile. A directory with unrelated files uses an
`Operon` child; collisions use `Operon-2`, `Operon-3`, and so on. A previously
managed child is reused. Existing files are never cleared to make room. The actual
directory appears in the GUI and result JSON. Use that directory for uninstall:

```powershell
$arguments = @('--uninstall', '--quiet', '--install-dir', ('"{0}"' -f $installed.installDir))
Start-Process -FilePath (Resolve-Path '.\Operon_Setup.exe') `
    -ArgumentList $arguments -NoNewWindow -Wait -PassThru
```

Run unattended uninstall from the original Setup outside the installation so it
can remove the installed helper too. Running `Operon_Uninstall.exe --quiet` from
inside the installation returns the actual result but retains its own executable
until it can be removed after exit. Uninstall keeps profiles and analysis results.
A failed/cancelled graphical
installation unlocks the directory field and **Change** button; edit the location
and retry in the same window. Its disabled action button visibly says **Installing**
during work. No automatic administrator elevation or system-Python changes occur.
The private Windows runtime uses extended-length import aliases so a nested
installation can load native wheels without changing the machine's long-path
policy. Dependency workers use the same path support with `.pth` execution disabled.

## Linux server

Use `scripts/install_server.sh` and `scripts/install_server.py` together from the
source archive/checkout. Bash, tar, and sha256sum are required. With Python 3.11+
available, the installer creates a private venv. Without it, Linux x86_64 uses the
same checksum-pinned micromamba bootstrap as managed SSH deployment and creates
a complete Python runtime inside the installation. This needs curl or wget and
network access; it does not require sudo, Conda, a graphical session or shell-profile
changes. Other Linux architectures require an explicitly supplied Python 3.11+.

```sh
# Install the latest stable application's and library's checksum-verified wheels.
bash scripts/install_server.sh --prefix "$HOME/apps/operon" \
  --result "$PWD/server-install.json"

# Or install the checkout being tested, including its independent library.
bash scripts/install_server.sh --source . --prefix "$HOME/apps/operon-test"

# Or choose an existing Python and local release wheels.
python3 scripts/install_server.py --python /path/to/python3.11 \
  --app-wheel /path/to/operon_studio-VERSION-py3-none-any.whl \
  --library-wheel /path/to/operon_builtin_library-LIBRARY_VERSION-py3-none-any.whl \
  --prefix "$HOME/apps/operon"
```

`--version VERSION` pins a downloadable release. Application and library versions
are independent; the matching library asset is read from that release. To avoid
package-index access, supply local application/library wheels and `--wheel-dir`
containing **all transitive dependency wheels** for that platform/Python. A source
install also needs its build requirements there. Bootstrapping Python still needs
network access unless `--python` is available.

Progress and the installation-log path are printed to stderr. Final stdout is
JSON with `status`, `install_dir`, `python`, `workspace`, `server_document`,
`command`, and `log`. Failures return exit code 1; invalid options return 2.
The default prefix is `~/.local/share/operon/server`. A populated unmanaged prefix
uses an `Operon` child without removing files. The result reports the actual path.

Run the `command` shown in the result; its launcher selects the installed Python
and workspace automatically. For example, with an initially empty explicit prefix:

```sh
"$HOME/apps/operon/bin/operon" --version
"$HOME/apps/operon/bin/operon" workflow init "$HOME/apps/operon/workspace/my-project"
cd "$HOME/apps/operon/workspace"
"$HOME/apps/operon/bin/operon" environment check my-project/workflow.yaml
"$HOME/apps/operon/bin/operon" environment prepare my-project/workflow.yaml
"$HOME/apps/operon/bin/operon" run my-project/workflow.yaml --progress --brief
```

The generated `server.json` uses the existing SSH handshake protocol. A Windows
desktop can select **Existing installation** and use the returned `install_dir`
as its server base. Reconnects read that document rather than reinstalling.

Reinstalling creates another runtime and retains previous runtimes, the server
identity and the selected workspace. Finish active work before upgrading. Failed
attempts retain their log under `versions/<attempt>/install.log`; they do not
delete previous runtimes or workflow files. An edited launcher is not overwritten.
The installer does not scan or eagerly install the whole operator library, Hi-C
toolchain, model weights or R environments. See [server CLI](server_cli.md) for
route preparation, explicit native-tool setup, task history and memory management.
