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
  0.7321, complex_plddt 0.8852. Boltz-2 weights were not downloaded.

## How to unblock

1. Provide network access to `huggingface.co` (or mirror the Boltz weights into
   `~/.boltz`) and rerun `boltz_predict` on a two-chain complex.
2. Fetch AntiFold `model.pt` from OPIG on a faster link and place it under the
   AntiFold package `models/` directory, or pass a checkpoint path when the
   operator grows one.
3. Place `Pfam-A.hmm` (pressed) locally and run `hmmer_domains`.

Until then these stay documented as gated; no easy substitute operator is added
to fill a batch.
