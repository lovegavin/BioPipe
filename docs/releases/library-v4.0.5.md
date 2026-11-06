# BioPipe Operator Library v4.0.5

Patch release for the 4.0 line. Operator behaviour is unchanged; this release
ships root-level installers for the dependencies declared by the library.

- Application / frontend: **2.6.0** (minimum and build)
- Protocol: **v3**
- Registry: 717 operators / 101 Readers / 7 packages / 24 routes

## Dependency installers (new)

| File | Platform |
|---|---|
| `install-dependencies.sh` | Linux / macOS |
| `install-dependencies.ps1` | Windows PowerShell 5.1+ |
| `install_dependencies.py` | shared implementation |

The installers use the library's own dependency session, so they repair exactly
what Studio's **Repair dependencies** button repairs. Python packages are
installed into immutable per-operator targets under the active profile.

```bash
./install-dependencies.sh --profile-dir /srv/biopipe --dry-run
./install-dependencies.sh --profile-dir /srv/biopipe
./install-dependencies.sh --profile-dir /srv/biopipe --tools
```

```powershell
.\install-dependencies.ps1 -ProfileDir C:\BioPipe -DryRun
.\install-dependencies.ps1 -ProfileDir C:\BioPipe -Tools
```

`--tools` creates `managed-v1/env-tools` with QUAST, minced, Flye, Infernal,
tRNAscan-SE, Foldseek, samtools, BWA, minimap2, DSSP and Vina; `--heavy` adds
antiSMASH and AMRFinderPlus. `--isolated` creates the declared ESM-3, Boltz and
AntiFold environments. Databases and model weights are never downloaded by
these scripts: they remain explicit resource steps.

## Assets

- Linux and Windows `.biopipe-library.zip`
- seed wheel
- `QUICKSTART.md`, `QUICKSTART.zh.md`
- `install-dependencies.sh`, `install-dependencies.ps1`, `install_dependencies.py`
- `SHA256SUMS.txt` and both verification reports
