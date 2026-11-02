# Large resources

BioPipe does not ship model weights, sequence databases or third-party
checkouts. Operators that need them read the shipped manifest
`biopipe/resources.json`, which records where each resource may live, which
environment variable overrides the search path, and exactly which files a
dependent operator expects. Nothing is downloaded automatically.

## ESMFold

`esmfold_predict` uses `fair-esm`'s ESMFold-3B. The weights are a single
2.77 GB file that `torch.hub` caches by name:

```bash
mkdir -p ~/.cache/torch/hub/checkpoints
curl -L -o ~/.cache/torch/hub/checkpoints/esmfold_3B_v1.pt \
  https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v1.pt   # 2.77 GB
```

fair-esm 2.0.0 needs four small compatibility fixes for Python 3.12 and for
the released checkpoint, all applied in site-packages:

1. `esm/esmfold/v1/trunk.py`: `structure_module` default becomes
   `field(default_factory=StructureModuleConfig)`.
2. `esm/esmfold/v1/esmfold.py`: `trunk` default becomes
   `field(default_factory=FoldingTrunkConfig)`.
3. `esm/esmfold/v1/pretrained.py`: remap checkpoint keys by inserting
   `.linear` into `ipa.linear_q_points.*` and `ipa.linear_kv_points.*`.
4. OpenFold must be importable (ESMFold imports `openfold.np`); add a `.pth`
   that points at a directory containing only the `openfold` package (not the
   checkout root, whose `scripts/` would shadow BioPipe's).

## OpenFold

OpenFold needs a checkout, the finetuning weights, and (on CPU) two small
patches because the official code imports its CUDA attention kernel
unconditionally.

```bash
git clone https://github.com/aqlaboratory/openfold /home/gavin/tools/openfold
python -m pip install dllogger ml-collections biotite modelcif einops   # dllogger may need git+https://github.com/NVIDIA/dllogger.git
curl -L -o /home/gavin/models/openfold/finetuning_ptm_2.pt \
  https://openfold.s3.amazonaws.com/openfold_params/finetuning_ptm_2.pt   # 358 MB
```

CPU patches applied to the checkout (GPU installs with a built kernel do not
need them): wrap `attn_core_inplace_cuda = importlib.import_module(...)` in
try/except in `openfold/utils/kernel/attention_core.py` and
`openfold/model/structure_module.py`, replace the in-place softmax calls with
`torch.softmax`/`self.softmax` when the kernel is absent, and wrap the
TensorRT import in `openfold/utils/script_utils.py`. Templates need a
directory with at least one `.cif`; the operator writes a dummy file when no
template directory is given.

## Boltz

Boltz downloads its own weights into a cache directory (default `~/.boltz`).
Hugging Face is unreachable from some networks; the `hf-mirror.com` mirror
serves the same files with the same names:

```bash
mkdir -p ~/.boltz
base=https://hf-mirror.com/boltz-community
curl -L -o ~/.boltz/ccd.pkl           $base/boltz-1/resolve/main/ccd.pkl
curl -L -o ~/.boltz/boltz1_conf.ckpt  $base/boltz-1/resolve/main/boltz1_conf.ckpt
curl -L -o ~/.boltz/boltz2_conf.ckpt  $base/boltz-2/resolve/main/boltz2_conf.ckpt
curl -L -o ~/.boltz/boltz2_aff.ckpt   $base/boltz-2/resolve/main/boltz2_aff.ckpt
curl -L -o ~/.boltz/mols.tar          $base/boltz-2/resolve/main/mols.tar
```

Sizes: ccd 330 MB, boltz1 3.6 GB, boltz2 conf 2.29 GB, boltz2 affinity
2.06 GB, mols 1.86 GB. With the cache populated, `boltz_predict` runs offline.
Boltz-2 affinity predictions require `properties: - affinity: {binder: B}` in
the YAML; `boltz_affinity_summary` tabulates the resulting
`affinity_<id>.json` files.

## AntiFold

AntiFold ships its weights separately from the Python package.

```bash
python -m pip install antifold==0.3.1
mkdir -p "$(python -c 'import antifold, pathlib; print(pathlib.Path(antifold.__file__).parent)')"/trained_models
curl -L -o "$(python -c 'import antifold, pathlib; print(pathlib.Path(antifold.__file__).parent)')"/trained_models/model.pt \
  https://opig.stats.ox.ac.uk/data/downloads/AntiFold/models/model.pt
```

The file is 566 838 063 bytes (566 MB). The `antifold_design` operator runs the
official `antifold.main` entry point; without the weights it fails with the
package's own error, and the gated real test stays skipped.

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

## Prodigal

Install the gene predictor from the distribution packages; no database is
required.

```bash
sudo apt-get install -y prodigal   # Debian/Ubuntu, Prodigal 2.6.3
prodigal -v
```

The default path is `prodigal` on `PATH`; override it with the operator's
`prodigal_path` parameter. `BIOPIPE_PRODIGAL_REAL=1` enables the real genome
check in `tests/test_extension252.py`.

## Pfam

`hmmer_domains` needs a pressed HMM database. The full Pfam-A release is about
418 MB compressed and 2.2 GB after decompression.

```bash
mkdir -p ~/db && cd ~/db
curl -LO https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.gz
gunzip Pfam-A.hmm.gz
hmmpress Pfam-A.hmm
export BIOPIPE_PFAM_HMM=~/db/Pfam-A.hmm
```

The real check in `tests/test_extension253.py` runs only when
`BIOPIPE_PFAM_HMM` points at the pressed database.
