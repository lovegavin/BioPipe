# BioPipe Quick Start

From a clean Windows machine to an exported, biologically meaningful result in
about five minutes: install the desktop application, import the current operator
library, and run a real structure-analysis workflow on the RCSB entry **1MEL**.

BioPipe runs locally. It does not upload your data and does not require Python to
be installed separately.

## 1. Install the desktop application

1. Download **`BioPipe_Setup.exe`** from the
   [v2.6.0 release](https://github.com/lovegavin/BioPipe/releases/tag/v2.6.0)
   (about 793 MB).
2. Run it. Windows SmartScreen may warn that the publisher is unknown; choose
   **More info → Run anyway**. The installer is not code-signed yet.
3. The installer is per-user: it installs under
   `%LOCALAPPDATA%\Programs\BioPipe Studio` and creates a desktop shortcut.
   No administrator rights are required.
4. Each installation gets a clean profile under
   `%USERPROFILE%\.biopipe\profiles\<installation-id>`; reinstalling keeps the old
   profile and your analysis files.

Supported platform: 64-bit Windows 10 or 11.

## 2. Import the operator library

The application ships a small seed library so that it opens on first launch. The
validated library for this release is **4.0.2** — 717 operators and 101 Readers.

1. Download **`BioPipe-Library-v4.0.2-Windows.biopipe-library.zip`** from the
   [library-v4.0.2 release](https://github.com/lovegavin/BioPipe/releases/tag/library-v4.0.2).
   On Linux use the `Linux` zip instead.
2. In Studio open **Operator Library → Import package**.
3. Select the zip and wait for the import to finish. The library panel then shows
   version **4.0.2**, independent of the application version.
4. The import is additive and transactional: if it fails, the previous library
   remains active.

Command-line equivalent (Python environment with BioPipe installed):

```bash
biopipe plugin install BioPipe-Library-v4.0.2-Windows.biopipe-library.zip
```

## 3. Run the example workflow

The quickstart pack on the release page (`BioPipe-Quickstart-v4.0.2.zip`) contains
the two input files and a ready-to-import graph.

**Inputs** (both public):

| File | Content |
| --- | --- |
| `data/vhh_1mel.pdb` | RCSB entry [1MEL](https://doi.org/10.2210/pdb1MEL/pdb): a camelid VHH domain (chains A, B) bound to hen egg-white lysozyme (chains L, M); 3,908 atoms |
| `data/vhh.fasta` | The 132-residue VHH sequence of chain A |

**Graph** (`vhh_interface.route.json`):

```
vhh_1mel.pdb ──▶ structure_interface_core ──▶ export_results (interface_residues.csv)
vhh.fasta   ──▶ sequence_liability_scan ──▶ export_results (liabilities.csv)
```

`structure_interface_core` computes the buried solvent-accessible surface of every
residue at the VHH/lysozyme interface and classifies each residue as core or rim.
`sequence_liability_scan` flags oxidation, isomerization and deamidation motifs in
the VHH sequence. The workflow takes a few seconds on a laptop CPU.

### Option A — canvas

1. Unzip the quickstart pack.
2. In Studio choose **File → Import workflow bundle or JSON** and select
   `vhh_interface.route.json`.
3. Select each **Source** node and point it at the corresponding file from
   `data/` (the graph stores paths relative to the pack, so they must be
   re-selected once after import).
4. Press **Run**.

### Option B — command line (source checkout)

From the repository root, where `library/` and `examples/` are present:

```bash
python -m biopipe --workspace "$PWD" run examples/quickstart/vhh_interface.route.json --wait
```

Exported files appear under `output/artifacts/exports/<hash>/`.

## 4. Expected results

| Quantity | Value |
| --- | --- |
| Interface residues | **88** |
| Core residues | **52** |
| Rim residues | **36** |
| Sequence liabilities | **10** (5 oxidation, 3 isomerization, 2 deamidation) |

Exported tables:

- `interface_residues.csv` — 88 rows; columns
  `residue,delta_sasa,isolated_sasa,buried_fraction,is_core`.
- `liabilities.csv` — 10 rows; columns
  `liability,position,severity_code,motif_length`.

The first interface row is `A:ILE:29` (buried fraction 0.537); the first liability
is `33:oxidation` (motif `M` in context `PYCMGWF`).

## 5. Let an agent drive it

If you connected an agent through MCP (Studio's **Agent** panel generates the
configuration; see `docs/quickstart_full_flow.md`, section 5), paste this prompt:

```text
Read QUICKSTART.md and docs/agent_bootstrap.md before doing anything else.
Then call biopipe_status, list the open sessions, and inspect the current canvas
with biopipe_context. Do not modify anything yet.

Using the two files in this quickstart pack (examples/quickstart/data in a repository
checkout: vhh_1mel.pdb and vhh.fasta), propose
a four-operator graph:
  PdbReader -> structure_interface_core -> export_results (CSV)
  FastaReader -> sequence_liability_scan -> export_results (CSV)
Show me the operator parameters and the expected outputs, and wait for my
confirmation. After I confirm, run the graph, report n_interface/n_core/n_rim and
the liability counts, and list the exported files.
```

The agent must read the documentation first, inspect the canvas before editing,
make one revision-checked transaction, and wait for explicit approval before
starting a run. These rules are enforced by `docs/agent_bootstrap.md`.

## 6. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| SmartScreen blocks the installer | Choose **More info → Run anyway**; the installer is unsigned. |
| `Missing operator definition: export_results` | The workspace has no operator library. Launch Studio and import the library zip, or point `--workspace` at a repository checkout that contains `library/`. |
| A run stays `queued` with “Waiting for available host memory” | A long-running Studio instance can hold a stale memory snapshot. Quit Studio completely and reopen it; the host capacity is re-scanned at startup. |
| Import rejects the zip | Use the `.biopipe-library.zip` asset, not the seed `.whl`; the bundle verifies its own checksums and package versions. |

Logs: `%LOCALAPPDATA%\BioPipe\Setup\<timestamp>` for installation, and the job
directory under the profile for runs.
