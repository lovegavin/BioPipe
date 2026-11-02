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
- `antifold_score`: AntiFold `model.pt` (566,838,063 bytes) was assembled from
  three verified 8-connection slices (each byte-probed against the server; the
  final checkpoint loads 489 tensors). Real run on the 1MEL VHH chain A:
  132 residues, mean perplexity 2.707, 35 IMGT CDR residues, 5.9 s on CPU.
  The OPIG host caps each connection at ~15.6 KB/s, so parallel ranges are
  the only practical download path.
- `colabfold_predict`: the official AlphaFold-2 parameter tar (3,722,752,000
  bytes) was fetched from `storage.googleapis.com` with 64 parallel range
  connections at ~9.7 MB/s aggregate (683 s), extracted into
  `~/.cache/colabfold/params/`, and a 118-residue VHH was folded with
  `--msa-mode single_sequence` in 15 s on CPU (pLDDT 32, pTM 0.252). The
  operator run returned mean pLDDT 31.94, pTM 0.210, max PAE 29.33 in 18.5 s.
  ColabFold 1.6.3 rejects `--device`; the wrapper now selects the device
  through `CUDA_VISIBLE_DEVICES` only.

- `structure_openmm_energy`: OpenMM 8.6.1 + PDBFixer build an amber14-all
  system with the GBn2 implicit solvent for a 973-atom VHH chain. Potential
  energy falls from **2804.88** to **-15738.28 kJ/mol** (gradient 66341.7 ->
  5857.1 kJ/mol/nm, delta -18543.16), 1881 particles, 6 force terms, 70.6 s
  on CPU. OpenMM itself is the oracle, and the operator recomputes both
  energies and gradients from its own Context.

## How to unblock

1. Provide network access to `huggingface.co` (or mirror the Boltz weights into
   `~/.boltz`) and rerun `boltz_predict` on a two-chain complex.
2. Fetch AntiFold `model.pt` from OPIG on a faster link and place it under the
   AntiFold package `models/` directory, or pass a checkpoint path when the
   operator grows one.
3. `hmmer_domains`: verified. `Pfam-A.hmm.gz` (418,160,514 bytes) was fetched
   from `ftp.ebi.ac.uk` with 32 parallel ranges (~1.2 MB/s), decompressed to a
   2.1 GB HMM and pressed with `hmmpress` (h3f 508 MB, h3i 2.9 MB, h3m 886 MB,
   h3p 1.1 GB). A 132-residue VHH scan completes in 0.42 s and returns four
   domains: `V-set`, `I-set`, `I-set`, `Ig_3` — the expected immunoglobulin
   superfamily assignment. Test 253 now clears `BIOPIPE_PFAM_HMM` for the
   validation branch so the suite is environment-neutral.

Until then these stay documented as gated; no easy substitute operator is added
to fill a batch.
