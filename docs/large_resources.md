# Large resources

Operon does not ship model weights, sequence databases or third-party
checkouts. Operators that need them read the shipped manifest
`src/task/step/steps/resources.json`, which records where each resource may live, which
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
   checkout root, whose `scripts/` would shadow Operon's).

## OpenFold

OpenFold needs a checkout, the finetuning weights, and (on CPU) two small
patches because the official code imports its CUDA attention kernel
unconditionally.

```bash
mkdir -p "$HOME/tools" "$HOME/models/openfold"
git clone https://github.com/aqlaboratory/openfold "$HOME/tools/openfold"
python -m pip install dllogger ml-collections biotite modelcif einops   # dllogger may need git+https://github.com/NVIDIA/dllogger.git
curl -L -o "$HOME/models/openfold/finetuning_ptm_2.pt" \
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

* root: `OPERON_PROTEINMPNN_PATH` (default `~/.local/share/operon/resources/proteinmpnn`)
* files: `protein_mpnn_run.py`, `vanilla_model_weights/v_48_020.pt`

```bash
git clone https://github.com/dauparas/ProteinMPNN.git
cd ProteinMPNN && curl -L -o vanilla_model_weights/v_48_020.pt \
  https://github.com/dauparas/ProteinMPNN/raw/main/vanilla_model_weights/v_48_020.pt
```

### ligandmpnn — LigandMPNN official checkout

* root: `OPERON_LIGANDMPNN_PATH`
* files: `run.py`, `model_params/ligandmpnn_v_32_010_25.pt`

### esm2 / esm_if1 — Meta ESM checkpoints

* root: `OPERON_ESM_MODEL_DIR` (defaults to the respective `esm2` or `esm_if1` directory below `~/.local/share/operon/resources`)
* files: `esm2_t6_8M_UR50D.pt`, `esm_if1_gvp4_t16_142M_UR50.pt`

```bash
curl -L https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t6_8M_UR50D.pt -O
curl -L https://dl.fbaipublicfiles.com/fair-esm/models/esm_if1_gvp4_t16_142M_UR50.pt -O
```

### esmfold — ESMFold 3B checkpoint

* root: `OPERON_ESMFOLD_WEIGHTS` or the torch hub cache
  (`~/.cache/torch/hub/checkpoints`)
* file: `esmfold_3B_v1.pt` (~2.5 GB)

`esmfold_predict` calls `esm.pretrained.esmfold_v1()`, which downloads this file
on first use. Pre-populate the cache to run offline.

### colabfold — ColabFold local installation

* root: `OPERON_COLABFOLD_PATH` (directory holding the `colabfold_batch` binary)
* file: `colabfold_batch`

```bash
pip install "colabfold[alphafold]"
# MMseqs2 and UniRef30 databases: see the ColabFold README "Local installation"
```

### alphafold2 — AlphaFold2 parameters

* root: `OPERON_ALPHAFOLD_DATA`
* file: `params/params_model_1_ptm.npz`

### rfdiffusion — RFdiffusion official checkout

* root: `OPERON_RFDIFFUSION_PATH`
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
mkdir -p "$HOME/tools/foldseek" && cd "$HOME/tools/foldseek"
curl -sL -o fs.tar.gz https://github.com/steineggerlab/foldseek/releases/download/10-941cd33/foldseek-linux-avx2.tar.gz
tar xzf fs.tar.gz          # ./foldseek/bin/foldseek
mkdir -p db && cp *.pdb db/
/absolute/path/foldseek/bin/foldseek createdb db mydb
```

Then set `foldseek_path=/absolute/path/foldseek/bin/foldseek` and
`database_path=/absolute/path/mydb`. To run the real integration test set
`OPERON_FOLDSEEK_BIN` and `OPERON_FOLDSEEK_DB`; otherwise the test skips.

## Prodigal

Install the gene predictor from the distribution packages; no database is
required.

```bash
sudo apt-get install -y prodigal   # Debian/Ubuntu, Prodigal 2.6.3
prodigal -v
```

The default path is `prodigal` on `PATH`; override it with the operator's
`prodigal_path` parameter. `OPERON_PRODIGAL_REAL=1` enables the real genome
check in `tests/test_extension252.py`.

## Pfam

`hmmer_domains` needs a pressed HMM database. The full Pfam-A release is about
418 MB compressed and 2.2 GB after decompression.

```bash
mkdir -p ~/db && cd ~/db
curl -LO https://ftp.ebi.ac.uk/pub/databases/Pfam/current_release/Pfam-A.hmm.gz
gunzip Pfam-A.hmm.gz
hmmpress Pfam-A.hmm
export OPERON_PFAM_HMM=~/db/Pfam-A.hmm
```

The real check in `tests/test_extension253.py` runs only when
`OPERON_PFAM_HMM` points at the pressed database.

## ESM-3

Install the official package (PyPI does not carry it) and fetch the open
weights through a reachable Hugging Face endpoint:

```bash
python -m pip install "esm @ git+https://github.com/evolutionaryscale/esm.git"
export HF_ENDPOINT=https://hf-mirror.com
python -c "import torch; from esm.models.esm3 import ESM3; ESM3.from_pretrained('esm3_sm_open_v1', device=torch.device('cpu'))"
```

The cache lands under `~/.cache/huggingface/hub/models--EvolutionaryScale--esm3-sm-open-v1`.
`OPERON_ESM3_REAL=1` enables the real check in `tests/test_extension325.py`.

## Provisioning

`python scripts/provision_resources.py --root <dir> [--only ID] [--mirror URL] [--jobs N] [--from-dir STAGING] [--offline]` downloads, copies or verifies the declared files with resume, retries and SHA-256 checks. See [the agent guide](agent_environment_repair.md) for the decision tree and the slow-uplink workflow.

## Dedicated operator environments

Operators whose upstream pins conflict with the shared scientific runtime use a
dedicated interpreter instead of downgrading NumPy/Torch:

```bash
python -m operon.environments            # status of every declared environment
python -m operon.environments --json
```

AntiFold (`antifold_design`) lives in `<prefix>/external/antifold`; the managed
installer creates it, installs `antifold==0.3.1` with `--no-deps` plus its
runtime pins, and the operator resolves that interpreter automatically. Override
with `OPERON_ENV_ANTIFOLD=/path/to/python` or the `python_executable` parameter.
Place the 541 MB weights at
`<prefix>/external/antifold/lib/python3.11/site-packages/antifold/trained_models/model.pt`
(download URL in `library/seed/operon/environments.json`).

## Multi-environment operators (resolution and overrides)

Operators whose upstream pins cannot coexist with the shared runtime declare
`resources.environment = "<name>"`; the list lives in `library/seed/operon/environments.json`.

Resolution order for `<name>`:

1. `OPERON_ENV_<NAME>` — absolute path to that interpreter.
2. `OPERON_ENVIRONMENTS_ROOT` / `<name>` (defaults to `<prefix>/external/<name>`),
   using `bin/python` on POSIX and `Scripts/python.exe` on Windows.

The runner resolves the environment before importing the operator, then executes
it through `operon.env_worker` in that interpreter: input Forms are written as
`.npy` plus JSON metadata (label encoders as mappings), the worker returns the
output Form the same way, and the host process never imports the conflicting
modules. The child process receives `PYTHONPATH=<OPERON_CODE_ROOT or detected
source tree>` and `HF_ENDPOINT` (default `https://hf-mirror.com`) so weight
downloads work behind a blocked Hugging Face.

Inspect and verify:

```bash
python -m operon.environments --json
python -m operon.environments            # OK/FAIL per environment
```

Per-operator table (generated pages also print the environment):

| Operator | Environment | Interpreter pins | Weight / data |
| --- | --- | --- | --- |
| `antifold_design`, `antifold_score` | `antifold` | Python 3.11, NumPy 1.26.4, Torch 2.3.1, Biotite 0.38, Biopython 1.83 | `antifold/trained_models/model.pt` (541 MB) |
| `esm3_embedding`, `esm3_inverse_folding`, `esm3_fold`, `esm3_sequence_generation`, `esm3_secondary_structure`, `esm3_sasa_prediction` | `esm3` | Python 3.12, Torch 2.6+ (the bridge tolerates 3.2.2 with torch 2.6), transformers, ESM from GitHub | ESM-3 open weights via HF mirror |
| `foldseek_align`, `foldseek_cluster` | shared | binary `foldseek` on `PATH` (`resources.external_tools`) | local database |
| `boltz_predict`, `boltz_complex_confidence`, `boltz_affinity_summary` | `boltz` (validated clone of the shared stack) | same versions as the shared runtime | `~/.boltz/{ccd.pkl,boltz1_conf.ckpt,boltz2_*.ckpt,mols.tar}` |

`python scripts/check_resources.py` prints large-data status; `python -m
operon.environments` prints interpreter status. A missing environment is a hard
failure for its operators, never a silent fallback.

## Genome annotation databases

| Resource | Operator | Install | Environment / default |
| --- | --- | --- | --- |
| antiSMASH 8 module databases | `antismash_bgc` | `conda install -c conda-forge -c bioconda antismash=8.0.4`, then `download-antismash-databases --database-dir ~/tools/antismash_db` | `OPERON_ANTISMASH_DB`, default `~/tools/antismash_db` |
| Rfam covariance models | `rfam_scan` | download `Rfam.cm.gz`, `gunzip Rfam.cm.gz`, then `cmpress Rfam.cm` | `OPERON_RFAM_DB`, default `~/tools/rfam` |
| AMRFinderPlus database | `amrfinder_plus` | `amrfinder_update -d ~/tools/amrfinder_db` | `OPERON_AMRFINDER_DB`, default `~/tools/amrfinder_db/<version>` |
| tRNAscan-SE 2.x | `trnascan_se` | `apt install trnascan-se` (or a bioconda environment) | binary on `PATH` |

The antiSMASH conda package deliberately ships **no** databases; run the official
downloader once (about 900 MB, ClusterBlast is the largest component). Rfam.cm is
about 330 MB after pressing, and the AMRFinderPlus database is versioned, so point
the environment variable at the version directory that contains `AMRProt.fa` and
`AMR.LIB`. All four operators prepend the resolved tool's own `bin` directory to
`PATH`, so helper binaries (`diamond`, `blastp`, `hmmpfam2` for antiSMASH and
`blastp` for AMRFinderPlus) resolve inside a conda environment without activating it.

## Genome assembly tools

The assembly operators call the official command-line tools and do not ship
binaries. Install them into a dedicated environment and put its `bin` on
`PATH` (or point `flye_path` / `quast_path` / `minced_path` at the executable):

```bash
conda create -n assembly -c conda-forge -c bioconda \
  flye=2.9.6 quast=5.3.0 minced=0.4.2 minimap2 openjdk=17
conda activate assembly
```

- `flye_assemble` needs `flye` plus `minimap2` on PATH.
- `assembly_stats` runs `quast` (QUAST 5.3); pass `reference_path` for
  reference-based metrics such as genome fraction and NGA50.
- `crispr_array_detect` runs `minced`, a Java program; the operator adds the
  tool directory to PATH so a bundled `java` is found.
