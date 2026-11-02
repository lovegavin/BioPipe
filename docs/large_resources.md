# Large resources

BioPipe does not ship model weights, sequence databases or third-party
checkouts. Operators that need them read the shipped manifest
`biopipe/resources.json`, which records where each resource may live, which
environment variable overrides the search path, and exactly which files a
dependent operator expects. Nothing is downloaded automatically.

## Workflow: download once, verify, then run

1. Download the resource once, outside the project tree.
2. Point the matching environment variable at the directory (or rely on the
   default roots listed below).
3. Verify with `python scripts/check_resources.py`; it prints `OK`, `PARTIAL` or
   `MISSING` per resource, the resolved directory and the install command.
4. Run the operator. A missing file now fails with the install command and the
   expected path instead of a bare `FileNotFoundError`.

`resource_preflight` exposes the same check inside a workflow: it emits one row
per expected file with its presence and size and records the remedy in
`info["missing_resources"]`.

## Manifest fields

| field | meaning |
| --- | --- |
| `id` | stable identifier used by `--resource` and `resource_preflight` |
| `env` | environment variable that overrides the search root |
| `roots` | directories probed in order when the variable is unset |
| `files` | files that must exist below the root |
| `install` | copy-paste installation command (quoted by the error message) |
| `url` | official source |

## Resources

### proteinmpnn — ProteinMPNN official checkout

* root: `BIOPIPE_PROTEINMPNN_PATH` (defaults `/home/gavin/tools/ProteinMPNN`, `D:/tools/ProteinMPNN`)
* files: `protein_mpnn_run.py`, `vanilla_model_weights/v_48_020.pt`

```bash
git clone https://github.com/dauparas/ProteinMPNN.git
cd ProteinMPNN && curl -L -o vanilla_model_weights/v_48_020.pt \
  https://github.com/dauparas/ProteinMPNN/raw/main/vanilla_model_weights/v_48_020.pt
```

### ligandmpnn — LigandMPNN official checkout

* root: `BIOPIPE_LIGANDMPNN_PATH`
* files: `run.py`, `model_params/ligandmpnn_v_32_010_25.pt`

### esm2 / esm_if1 — Meta ESM checkpoints

* root: `BIOPIPE_ESM_MODEL_DIR` (defaults `/home/gavin/models`, `D:/models`)
* files: `esm2_t6_8M_UR50D.pt`, `esm_if1_gvp4_t16_142M_UR50.pt`

```bash
curl -L https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t6_8M_UR50D.pt -O
curl -L https://dl.fbaipublicfiles.com/fair-esm/models/esm_if1_gvp4_t16_142M_UR50.pt -O
```

### esmfold — ESMFold 3B checkpoint

* root: `BIOPIPE_ESMFOLD_WEIGHTS` or the torch hub cache
  (`~/.cache/torch/hub/checkpoints`)
* file: `esmfold_3B_v1.pt` (~2.5 GB)

`esmfold_predict` calls `esm.pretrained.esmfold_v1()`, which downloads this file
on first use. Pre-populate the cache to run offline.

### colabfold — ColabFold local installation

* root: `BIOPIPE_COLABFOLD_PATH` (directory holding the `colabfold_batch` binary)
* file: `colabfold_batch`

```bash
pip install "colabfold[alphafold]"
# MMseqs2 and UniRef30 databases: see the ColabFold README "Local installation"
```

### alphafold2 — AlphaFold2 parameters

* root: `BIOPIPE_ALPHAFOLD_DATA`
* file: `params/params_model_1_ptm.npz`

### rfdiffusion — RFdiffusion official checkout

* root: `BIOPIPE_RFDIFFUSION_PATH`
* files: `scripts/run_inference.py`, `models/Complex_beta_ckpt.pt`

## Policy

* Weights and databases are user-supplied; the repository stores only the
  manifest and this page.
* Tests never download GB resources: wrappers are exercised with fake runners
  and injected loaders, and a real minimal run is performed only when the
  resource is already installed locally.
* Operators that consume a resource validate it up front, so a typo in a path
  surfaces before any expensive computation starts.

## Foldseek

Foldseek is a static binary and needs a database that the user builds or
downloads; the operator does not download anything.

```bash
mkdir -p /home/gavin/tools/foldseek && cd /home/gavin/tools/foldseek
curl -sL -o fs.tar.gz https://github.com/steineggerlab/foldseek/releases/download/10-941cd33/foldseek-linux-avx2.tar.gz
tar xzf fs.tar.gz          # ./foldseek/bin/foldseek
mkdir -p db && cp *.pdb db/
/absolute/path/foldseek/bin/foldseek createdb db mydb
```

Then set `foldseek_path=/absolute/path/foldseek/bin/foldseek` and
`database_path=/absolute/path/mydb`. To run the real integration test set
`BIOPIPE_FOLDSEEK_BIN` and `BIOPIPE_FOLDSEEK_DB`; otherwise the test skips.
