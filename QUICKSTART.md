# Operon Quick Start (Studio 3.0.2 + Operator Library 5.0.1)

From a clean Windows machine to an exported, biologically meaningful result in
about five minutes: install Operon Studio 3.0.2, import operator library 5.0.1,
and run a real VHH/lysozyme interface analysis on **1MEL**.

Operon runs locally. It does not upload your data and does not require a
separate Python installation.

## 0. Versions

| Component | Version |
| --- | --- |
| Desktop application / frontend | **3.0.2** |
| Operator library (backend) | **5.0.1** (867 operators, 108 Readers, 7 packages, 72 routes) |
| Protocol | v3 |
| Minimum application | 3.0.2 |

The application and the library upgrade independently: upgrading the application
never overwrites an imported library. The example below lives in the source
repository under `examples/quickstart/`; `QUICKSTART.md` and `QUICKSTART.zh.md`
ship both standalone and inside `Operon-Quickstart-v5.0.1.zip`.

## 1. Install Operon Studio 3.0.2

1. Download **`Operon_Setup.exe`** from the
   [v3.0.2 release](https://github.com/lovegavin/Operon/releases/tag/v3.0.2).
2. Run it. If SmartScreen warns that the publisher is unknown, choose
   **More info → Run anyway**. The installer is not code-signed yet.
3. Installation is per-user, under `%LOCALAPPDATA%\Programs\Operon Studio`,
   with desktop and Start menu shortcuts. No administrator rights are required.
4. Each installation gets its own profile under
   `%USERPROFILE%\.operon\profiles\<installation-id>`; reinstalling keeps the old
   profile untouched and starts a new, empty workspace.

The 3.0.2 installer ships a **management runtime** (HTTP/MCP/SSH plus NumPy for
memory and previews), not a complete scientific environment. Operator manifests,
code and documentation load without analysis packages; Pandas, SciPy, h5py and
similar dependencies are prepared explicitly for a route later, and the first
preparation needs internet access.

Supported: 64-bit Windows 10 / 11.

## 2. Import Operator Library 5.0.1

1. From the [library-v5.0.1 release](https://github.com/lovegavin/Operon/releases/tag/library-v5.0.1)
   download the package for your platform:
   - Windows: `Operon-Library-v5.0.1-Windows.operon-library.zip`
   - Linux: `Operon-Library-v5.0.1-Linux.operon-library.zip`
2. In Studio open **Operator Library → Import package** and select the zip.
3. The panel shows **5.0.1** when done. Import is transactional: a failure keeps
   the previous library.
4. The platform must match; a mismatch reports
   `Library source does not match wheel`.

> **Legacy suffix.** The file picker and upload endpoint also accept older
> `.biopipe-library.zip` archives, but installation routing is strict: only
> `.operon-library.zip` bundles (`format: "operon.library"`) install end to end.
> A legacy archive passes the picker and then fails installation, so use the
> 5.0.1 asset above. That gap is recorded in
> [docs/verification/operon-5.0.0-compatibility.md](docs/verification/operon-5.0.0-compatibility.md).

From an installed Python environment:

```bash
operon --profile-dir <profile> plugin install \
  Operon-Library-v5.0.1-Windows.operon-library.zip
```

Verify the registry:

```bash
operon --profile-dir <profile> registry check
# operators 867 / readers 108 / packages 7 / routes 72 / errors 0
```

`registry check` validates the protocol and registry, not analysis
dependencies; missing items appear in the dependency panel and are installed
only when you prepare the environment.

## 3. Import and run the example route

The data and route live in the source repository:

| File | Location | Size |
| --- | --- | --- |
| Structure | `examples/quickstart/data/vhh_1mel.pdb` | 361,017 B |
| Sequence | `examples/quickstart/data/vhh.fasta` | 145 B |
| Route | `examples/quickstart/vhh_interface.route.json` | — |

1MEL is a camelid VHH (chains A, B) bound to hen egg-white lysozyme (chains L,
M), 3,908 atoms; the FASTA is chain A, 132 residues. Both files are public
1MEL-derived inputs (sha256 `321aa847…24de4` and `7d148d84…4fa5`).

The route is self-contained: its `base_dir` is `examples/quickstart`, so the two
Source nodes resolve `data/vhh_1mel.pdb` and `data/vhh.fasta` when the repository
root is the workspace. If you copied the route somewhere else, select both
Source nodes and repoint them once.

Graph: two Sources → `structure_interface_core` (binder chains `A,B`, target
chains `L,M`, `core_fraction` 0.5, `probe_radius` 1.4, 92 surface points) and
`sequence_liability_scan` (oxidation plus deamidation/isomerization motifs,
±3 context) → two `export_results` CSV nodes.

### Canvas

1. Studio → **File → Import workflow bundle or JSON**, choose
   `vhh_interface.route.json`.
2. Click **Validate**. If the environment is blocked, prepare the route's
   dependencies once (biopython, h5py, hictkpy, numpy, scipy); Validate and Run
   never install anything themselves.
3. Click **Run**; about 4 s on a normal laptop CPU.

### Command line

From the repository root:

```bash
python -m operon --workspace "$PWD" \
  run examples/quickstart/vhh_interface.route.json --wait
```

Exports land in `output/artifacts/exports/<hash>/`.

## 4. Option: agent + MCP

Open Studio's **Agent panel**; it generates the MCP configuration for the current
profile. Paste a block like this into your agent client:

```json
{
  "mcpServers": {
    "operon": {
      "command": "<install dir>\\operon.exe",
      "args": ["mcp", "--allow-run"]
    }
  }
}
```

- `--allow-run` lets the agent submit jobs; use `--read-only` otherwise.
- Add `--allow-plugins` if the agent must install plugins.
- Restart the client after editing; the `operon_*` tools appear next session.

Verify the connection with `operon_status()`, `operon_sessions()` and
`operon_context(session_id)`: a response with the workspace and the 5.0.1
registry means the connection works.

## 5. Option: a remote Linux server

The desktop edits and displays; the server executes. Choose **Execution target →
Server maintenance → Install / upgrade server**, enter SSH host, port and user,
and confirm the host fingerprint. The installer creates an isolated Python 3.11
environment (micromamba, BWA, samtools, pairtools, cooler, cooltools) under
`$HOME/.local/share/operon`, needs no sudo and writes a reusable `server.json`.
Then switch the execution target and use Check / Run; results and logs stay in
Studio. On the agent path, use `operon_remote_status()`,
`operon_remote_ensure(profile_id)` and `operon_set_execution(...)` so
`operon_run` / `operon_submit` execute remotely.

## 6. Expected results and self-check

Verified with library 5.0.1 on 1MEL:

| Metric | Value |
| --- | --- |
| Interface residues | **88** |
| Core residues (`is_core = 1`) | **52** |
| Rim residues | **36** |
| Sequence liabilities | **10** (5 oxidation, 3 isomerization, 2 deamidation) |

- `interface_residues.csv`: 88 rows, columns
  `residue,delta_sasa,isolated_sasa,buried_fraction,is_core`; the first row is
  `A:ILE:29` with `buried_fraction ≈ 0.537` and `is_core = 1`.
- `liabilities.csv`: 10 rows, columns
  `liability,position,severity_code,motif_length`; the first row is
  `33:oxidation`.

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
| Agent has no `operon_*` tools | MCP configuration not active; check the command path and `--allow-run`, then restart the client. |
| `Missing operator definition: export_results` | The workspace has no loaded library; import 5.0.1 in Studio, or point `--profile-dir` at a profile that has it. |
| `Library source does not match wheel` | Wrong platform package; use the Windows or Linux 5.0.1 zip. The old library is kept. |
| `The selected execution environment is not ready` | Prepare dependencies explicitly for this route, then Validate again. Nothing is installed by Validate or Run. |
| Server installation fails | Read `managed-v1/setup-<digest>.log`; check SSH, disk and outbound HTTPS. |
| Jobs stay `queued` | A long-running Studio may hold a stale memory snapshot; fully restart it. |

Logs: installer logs under `%LOCALAPPDATA%\Operon\Setup\<timestamp>`, runtime
logs under the profile's `logs/`, server logs at
`managed-v1/setup-<digest>.log`.

## 8. Next steps

- 72 built-in routes in the 5.0.1 library: **File → Open route**.
- Parameters, ports and errors: select a node and open **Inspector** and the run log.
- Protocol and extensions: `docs/operator_protocol.md`,
  `docs/step_extensions.md`.
- Agent rules and tools: `docs/agent_bootstrap.md`, `docs/agent_api.md`.
