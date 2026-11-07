# BioPipe Quick Start (application 2.6.0 + operator library 4.0.4)

> This is the original, version-pinned library walkthrough. For the current
> **Operon 3.0.1** application, use the [Windows Setup guide](docs/windows_setup.md)
> or [Windows/Linux CLI installer](docs/command_line_installation.md), then
> explicitly [check and prepare the selected workflow environment](docs/readiness.md).
> Installation paths, installer names and bundled dependencies below describe 2.6.0.

From a clean Windows machine to an exported, biologically meaningful result in
about five minutes: install the desktop application, import operator library
4.0.4, and run a real VHH/lysozyme interface analysis on **1MEL**.

BioPipe runs locally. It does not upload your data and does not require a
separate Python installation.

## 0. Versions

| Component | Version |
| --- | --- |
| Desktop application / frontend | **2.6.0** |
| Operator library (backend) | **4.0.4** (717 operators, 101 Readers, 7 packages, 24 routes) |
| Protocol | v3 |
| Minimum application | 2.6.0 |

The application and the library upgrade independently: upgrading the application
never overwrites an imported library. Quick start ships only this file and
`QUICKSTART.zh.md`; the example data stays in the source repository.

## 1. Install the desktop application

1. Download **`BioPipe_Setup.exe`** from the
   [v2.6.0 release](https://github.com/lovegavin/BioPipe/releases/tag/v2.6.0)
   (about 793 MB).
2. Run it. If SmartScreen warns that the publisher is unknown, choose
   **More info → Run anyway**. The installer is not code-signed yet.
3. Installation is per-user, under `%LOCALAPPDATA%\Programs\BioPipe Studio`,
   with a desktop shortcut. No administrator rights are required.
4. Each installation gets its own profile under
   `%USERPROFILE%\.biopipe\profiles\<installation-id>`; reinstalling keeps it.

Supported: 64-bit Windows 10 / 11.

## 2. Import operator library 4.0.4

1. From the [library-v4.0.4 release](https://github.com/lovegavin/BioPipe/releases/tag/library-v4.0.4)
   download the package for your platform:
   - Windows: `BioPipe-Library-v4.0.4-Windows.biopipe-library.zip`
   - Linux: `BioPipe-Library-v4.0.4-Linux.biopipe-library.zip`
2. In Studio open **Operator Library → Import package** and select the zip.
3. The panel shows **4.0.4** when done. Import is transactional: a failure keeps
   the previous library.
4. The platform must match; a mismatch reports
   `Library source does not match wheel`.

From an installed Python environment:

```bash
biopipe --profile-dir <profile> plugin install \
  BioPipe-Library-v4.0.4-Windows.biopipe-library.zip
```

Verify the registry:

```bash
biopipe --profile-dir <profile> registry check
# operators 717 / readers 101 / packages 7 / routes 24 / errors 0
```

`registry check` validates the protocol and registry, not analysis
dependencies; install missing items from the dependency panel when you need
them. They are not required for this quick start.

## 3. Option one: agent + MCP (recommended)

### 3.1 Start the MCP server

Open Studio's **Agent panel**; it generates the MCP configuration for the current
profile. Paste a block like this into your agent client (Claude Desktop, Cursor,
DeepSeek Harness, ...):

```json
{
  "mcpServers": {
    "biopipe": {
      "command": "<install dir>\\biopipe.exe",
      "args": ["mcp", "--allow-run"]
    }
  }
}
```

- `command` is the absolute path shown by the panel; on Linux it is usually
  `biopipe` from the installed environment.
- `--allow-run` lets the agent submit jobs; use `--read-only` for read-only use.
- Add `--allow-plugins` if the agent must install plugins.
- Restart the agent client after editing the configuration; the `biopipe_*`
  tools appear in a new session.

### 3.2 Verify the connection

Call, in order:

```text
biopipe_status()             # connection, version, workspace
biopipe_sessions()           # open canvas sessions
biopipe_context(session_id)  # selected nodes, parameters, revision
```

A response with the workspace, 717 operators and 101 Readers means the
connection works.

### 3.3 Let the agent run 1MEL

Once connected, send this text to the agent **verbatim**:

```text
使用本快速开始包中的 vhh_1mel.pdb 与 vhh.fasta（源码仓库中位于examples/smoke_real_data/input），提出一个有深度研究价值的科学问题，先输出得到确认，再设计分析图，在远程服务器或本地运行，自行检查算子的输出与结果，得到严谨的科学结论
```

Notes (keep them outside the command):

- The data is under `examples/smoke_real_data/input/` in the source repository;
  without a checkout, use files with the same names anywhere on disk.
- The agent first proposes a scientific question and a graph, and runs only
  **after you confirm**. The execution target decides where it runs: locally, or
  on the server from section 4.
- The agent rules are in `docs/agent_bootstrap.md`: read the canvas first, edit
  in one transaction with `expected_revision`, wait for confirmation before
  running, and report only results from `biopipe_artifacts` /
  `biopipe_artifact_table`.

## 4. Option two: a remote Linux server

Use this when the data lives on a server or the laptop is too small. The desktop
edits and displays; the server executes.

### 4.1 First server installation

1. In the top toolbar choose **Execution target → Server maintenance → Install /
   upgrade server**.
2. Enter the SSH host, port and user; pick a key or password; confirm the host
   fingerprint on first connection.
3. The installer downloads micromamba and creates a Python 3.11 environment with
   BWA, samtools, pairtools, cooler and cooltools. It needs no sudo and does not
   modify the system Python.
4. The default install directory is `$HOME/.local/share/biopipe`; the run
   directory is `workspace/` below it. Both can be changed in the panel.
5. A successful install writes a stable `server.json`; later connections reuse
   it without reinstalling.

The install log is `managed-v1/setup-<digest>.log` on the server. A failed
attempt does not publish a new installation pointer; retry from the panel. To
register an existing environment:

```bash
python -m biopipe.remote.installation register \
  --app-dir /srv/biopipe --workspace /srv/biopipe-work
```

Then choose **Manually specify environment** on the desktop.

### 4.2 Run on the server

1. Switch the execution target in the toolbar.
2. Source nodes can browse server files; Check / Run execute over SSH.
3. Results and logs stay in Studio; no manual scp is needed.

### 4.3 Agent on the server

The agent still talks to the local Studio; switch the execution device:

```text
biopipe_remote_status()                 # is the profile connected?
biopipe_remote_ensure(profile_id)       # reconnect if needed
biopipe_set_execution(session_id, document_id, expected_revision,
                      {"kind": "ssh", "profile_id": "<id>"})
```

Then `biopipe_validate` / `biopipe_run` / `biopipe_submit` execute on the
server, and `biopipe_artifacts`, `biopipe_artifact_table`, `biopipe_logs` read
remote results directly.

## 5. Without an agent: canvas and CLI

The data and route live in the source repository:

| File | Location |
| --- | --- |
| Structure | `examples/smoke_real_data/input/vhh_1mel.pdb` |
| Sequence | `examples/smoke_real_data/input/vhh.fasta` |
| Route | `examples/quickstart/vhh_interface.route.json` |

1MEL is a camelid VHH (chains A, B) bound to hen egg-white lysozyme (chains L,
M), 3,908 atoms; the FASTA is chain A, 132 residues.

### Canvas

1. Studio → **File → Import workflow bundle or JSON**, choose
   `vhh_interface.route.json`.
2. Select both **Source** nodes and point them at
   `examples/smoke_real_data/input/vhh_1mel.pdb` and `.../vhh.fasta` (the route
   stores the old relative path, so re-select once after import).
3. Click **Run**; about 4 s on a normal laptop CPU.

### Command line

From the repository root, first change the two Source `path` values to
`examples/smoke_real_data/input/`, then:

```bash
python -m biopipe --workspace "$PWD" \
  run examples/quickstart/vhh_interface.route.json --wait
```

Exports land in `output/artifacts/exports/<hash>/`.

## 6. Expected results and self-check

| Metric | Value | Tolerance |
| --- | --- | --- |
| Interface residues | **88** | exact |
| Core residues | **52** | exact |
| Rim residues | **36** | exact |
| Sequence liabilities | **10** (5 oxidation, 3 isomerization, 2 deamidation) | exact |
| Whole-structure SASA (518 residues) | **21,803.1 Å²** | ±0.5% |

- `interface_residues.csv`: 88 rows, columns
  `residue,delta_sasa,isolated_sasa,buried_fraction,is_core`; the first row is
  `A:ILE:29` with `buried_fraction = 0.537` and `is_core = 1`.
- `liabilities.csv`: 10 rows, columns
  `liability,position,severity_code,motif_length`; the first row is
  `33:oxidation`, motif `M`, context `PYCMGWF`.

```python
import pandas as pd
i = pd.read_csv("interface_residues.csv")
l = pd.read_csv("liabilities.csv")
assert len(i) == 88 and int(i.is_core.sum()) == 52
assert abs(i.iloc[0].buried_fraction - 0.537) < 0.002
assert len(l) == 10 and l.iloc[0].liability == "33:oxidation"
print("OK", i.residue.iloc[0], l.liability.iloc[0])
```

## 7. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Agent has no `biopipe_*` tools | MCP configuration not active; check the command path and `--allow-run`, then restart the client. |
| `Missing operator definition: export_results` | The workspace has no loaded library; import 4.0.4 in Studio, or point `--profile-dir` at a profile that has it. |
| `Library source does not match wheel` | Wrong platform package; use the Windows or Linux zip. The old library is kept. |
| Server installation fails | Read `managed-v1/setup-<digest>.log`; check SSH, disk and outbound HTTPS. |
| Server connects but operators are unavailable | Import 4.0.4 into the server profile, or install dependencies from the panel. |
| Jobs stay `queued` | A long-running Studio may hold a stale memory snapshot; fully restart it. |

Logs: installer logs under `%LOCALAPPDATA%\BioPipe\Setup\<timestamp>`, runtime
logs under the profile's `logs/`, server logs at
`managed-v1/setup-<digest>.log`.

## 8. Next steps

- 24 built-in routes: **File → Open route**.
- Parameters, ports and errors: select a node and open **Inspector** and the run log.
- Protocol and extensions: `docs/operator_protocol.md`,
  `docs/step_extensions.md`.
- Agent rules and tools: `docs/agent_bootstrap.md`, `docs/agent_api.md`.
