# Hard-capability status

The library policy (see `extension_policy.md`) limits new work to capabilities
that are hard to implement or verify and analytically important. This page
records the current state of that queue, including what is blocked and why, so
nobody re-reports a blocked item as delivered.

## Verified

| Capability | Evidence |
| --- | --- |
| `foldseek_search` | Real run: Foldseek 10-941cd33 static binary + a local database built with `foldseek createdb` from two fixtures; 1MEL query returned 5 hits, top self-hit `alntmscore 1.008`. Real-run test activates with `BIOPIPE_FOLDSEEK_BIN`/`BIOPIPE_FOLDSEEK_DB`. |
| `proteinmpnn_*`, `ligandmpnn_*`, `esm_*`, `esmfold_predict`, `colabfold_predict` | Real weights and real runs from earlier batches. |

## Wrapper-aligned, weights unavailable here

| Capability | State |
| --- | --- |
| `boltz_predict` | Invocation now matches the real Boltz CLI (`--accelerator`, `--model`, `--output_format`, `--sampling_steps`, `--diffusion_samples`, `--num_workers`, `--use_msa_server`, `--no_kernels`; affinity is driven by the YAML `properties.affinity` block, not a CLI flag). Verified with a fake official-layout runner. Not run for real: Boltz downloads `ccd.pkl` and `boltz*_conf.ckpt` from `huggingface.co`, which resolves to a blackholed IPv4 (`199.59.149.203`) and an IPv6 address with no route in this WSL network, so `urllib` fails with `Network is unreachable`. |

## Blocked

| Capability | Blocker |
| --- | --- |
| `antifold_score` (AntiFold/ESM-IF antibody inverse folding) | The OPIG weights (`model.pt`, 566 MB) download at roughly 1.5 MB/min and stall; a partial 16 MB file was left after ~10 minutes. Not shippable as verified in this environment. |
| Boltz-2 real inference | Same HuggingFace network block as above (`huggingface.co` IPv4 blackholed). |
| OpenFold / AlphaFold-2 parameters | Parameter bundles are hosted on storage that is unreachable here; no local copy. |
| `hmmer_domains` real scan | `Pfam-A.hmm` (GB scale) is not present locally and its download source is unreachable. |

## Verified real runs

- `foldseek_search`: Foldseek `10-941cd33`, local database from two fixtures,
  1MEL query returns 5 hits (top self-hit alnTM 1.008).
- `boltz_predict`: Boltz-1 with local weights and `msa: empty` (CPU, 25 sampling
  steps): 14-residue peptide, PDB + `confidence_*.json`, confidence_score
  0.7321, complex_plddt 0.8852.
- `boltz_predict` with `model: boltz2` + `affinity: true`: peptide plus
  ethanol through the operator (CPU, 66 s). Output PDB + confidence
  (`confidence_score 0.8012`, `complex_plddt 0.9638`, `ligand_iptm 0.1505`)
  and `affinity_*.json` (`affinity_pred_value 1.906`,
  `affinity_probability_binary 0.1099`). Weights `boltz2_conf.ckpt`
  (2.29 GB), `boltz2_aff.ckpt` (2.06 GB) and `mols.tar` (1.86 GB) came from
  `hf-mirror.com`.

- `esmfold_predict` with `weights_dir`: the 3B checkpoint from
  `facebook/esmfold_v1` was downloaded through `hf-mirror.com`
  (`pytorch_model.bin` 8,442,062,570 bytes, sha256
  `2ee07356b125d1e3e57503c204111fd7323347fc4735d41d3caac57c2a78e116`), loaded
  with `transformers.EsmForProteinFolding`, and run on a 118-residue VHH:
  879 atoms, mean pLDDT 0.846, 33.7 s on CPU.
- AntiFold `model.pt` is now measurable rather than hung: the OPIG host caps
  each connection at ~15.6 KB/s, so 540 MB needs about ten hours; a partial
  21.7 MB file is a valid resumable base.
- ColabFold's AlphaFold-2 parameters are only served from
  `storage.googleapis.com` at ~91 KB/s (about eleven hours for 3.47 GB); the
  GitHub release asset named in the earlier note does not exist.

## How to unblock

1. Provide network access to `huggingface.co` (or mirror the Boltz weights into
   `~/.boltz`) and rerun `boltz_predict` on a two-chain complex.
2. Fetch AntiFold `model.pt` from OPIG on a faster link and place it under the
   AntiFold package `models/` directory, or pass a checkpoint path when the
   operator grows one.
3. Place `Pfam-A.hmm` (pressed) locally and run `hmmer_domains`.

Until then these stay documented as gated; no easy substitute operator is added
to fill a batch.
