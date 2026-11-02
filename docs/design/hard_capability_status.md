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

- `interface_mmgbsa_delta`: single-point MM/GBSA on the 1MEL A/B (VHH) versus
  L/M (lysozyme) complex, three OpenMM systems (7596 / 3762 / 3834 particles).
  Complex 8194.76, binder 9318.68, target -1198.10 kJ/mol, **delta 74.18**;
  nonbonded delta -4700.40, GB delta +4774.58 (desolvation), bonded delta
  exactly 0.00 — the bonded cancellation is the internal consistency check.
  4.8 s on CPU.

- `interface_alanine_scan`: computational alanine scanning on the same 1MEL
  complex. The scan re-uses `mmgbsa_terms`, truncates each interface residue to
  N/CA/C/O/CB, rebuilds hydrogens with PDBFixer, and reports
  `mutant_delta - wt_delta`. Five target-side residues in 28.2 s: wt delta
  115.55 kJ/mol, mutants 112.09 / 61.00 / 73.09 / 98.41 / 54.71, delta-delta
-3.47 / -54.55 / -42.46 / -17.14 / -60.84 kJ/mol. Hydrogen placement is not
  seeded, so absolute values shift slightly between runs; all values within a
  run share one wt baseline, which keeps the ranking comparable.

- `structure_protonation_pka`: pdb2pqr 3.8.0 with PROPKA 3.5.1. On the VHH
  chain A the operator returns 34 titratable residues, net charge -2.81
  (Henderson-Hasselbalch) versus -3.00 (PQR atom charges). On hen lysozyme
  chains L/M it reproduces the classic pattern: **Glu35 pKa 6.87 / 7.03**
  (elevated above the 4.5 model value) and Asp52 4.91 / 4.76 (normal), 74
  residues, net charge 15.49 versus 15.00. Per-residue HH and PQR charges can
  differ by up to ~0.5 because PDB2PQR protonates discretely while the
  operator's HH formula is fractional.

- `structure_openmm_md_stability`: OpenMM 8.6.1 + PDBFixer. VHH chain A
  (1881 particles, 907 constraints) minimised, heated to 300 K and run for
  500 equilibration + 1000 production steps (2 ps, 2 fs step) in 162 s on
  CPU: temperature rises **250 → 295 K** during production, RMSD stays
  **≈1.0 Å** from the minimised structure and the radius of gyration is flat
  (14.26 Å, change 0.01 Å). Trajectories are not bitwise reproducible
  because the CPU platform sums in parallel.

- `antifold_design`: antifold 0.3.1 with the OPIG `model.pt` weights (566 MB,
  downloaded from `opig.stats.ox.ac.uk`). On the 1MEL VHH/lysozyme complex
  (chains A against L, CDR1-3) the wild-type score is **1.5146**; five sampled
  designs at T=0.2 give recovery **0.857-0.865** with 12-13 substitutions each,
  and **67-69%** of the substitutions fall inside the Kabat CDRs (CDRs cover
  35% of the domain, so the model concentrates edits where expected). The
  per-residue profile covers 259 residues, 112 preferring a different residue,
  mean perplexity 3.71. Real inference takes about 5 s per structure on CPU.
  Biopython 1.88 compatibility for the shared Kabat aligner was fixed in the
  same release (the `end_gap_score` setter replaced the removed
  `end_insertion_score`/`end_deletion_score` attributes).

- `boltz_affinity_summary`: Boltz-2 (conf 2.29 GB + affinity 2.06 GB + mols
  1.86 GB, all fetched from `hf-mirror.com`) with an empty MSA. A 14-residue
  peptide plus aspirin ran **structure and affinity in 40 s on CPU**, writing
  `affinity_aff.json` with `affinity_pred_value 1.594`,
  `affinity_probability_binary 0.359`, and two auxiliary variant heads
  (1.726/0.204 and 1.461/0.516). The operator reproduces the table exactly
  and marks `has_variants = 1`. No structure prediction accuracy claim is
  made for this 14-residue toy system.

- `openfold_predict`: OpenFold `finetuning_ptm_2` (358 MB, from the public
  `openfold` S3 bucket) on a 14-residue peptide with single-sequence
  alignments: **94 atoms, 36.8 s on CPU**, pLDDT mean **68.7**
  (52.4-80.2) — the expected low confidence for a one-sequence peptide.
  The official code imports its CUDA attention kernel unconditionally; the
  operator documents the three small CPU patches (softmax fallback, TensorRT
  guard, dummy template CIF) in `docs/large_resources.md`. No accuracy claim
  is made without an experimental reference.

- `structure_ligand_geometry_qc`: RDKit covalent-radii bounds plus a cKDTree
  protein-clash scan. Aspirin from SMILES (21 atoms, 19-21 perceived bonds)
  passes with 0 outliers; a synthetic protein atom 1.2 A from the ligand gives
  **3 clashes** and a minimum distance of **1.2 A**. Known boundary: the PDB
  round trip re-perceives connectivity from distances, so a severely stretched
  bond can drop out of the perceived graph instead of being flagged; a template
  SMILES comparison is the next refinement.

- `structure_tm_score`: own implementation of the length-normalised TM-score
  (d0 = 1.24*cbrt(L-15)-1.8, iterative 4.5 A distance weighting) validated
  against `tmtools` (TM-align port) as the authoritative oracle: 1MEL copies
  A vs B give **0.9865 both** (132 C-alpha pairs, RMSD 0.51 A, all aligned),
  a 1.0 A noised copy gives **0.8652 both** (delta 0.0000), identity gives
  **1.000000 both**.

- `esmfold_predict`: fair-esm 2.0.0 with the 2.77 GB ESMFold-3B checkpoint.
  A 14-residue peptide on CPU: **94 atoms, 50.4 s**, mean pLDDT **73.3**
  (58.0-82.7), 2 recycles. Requires the four compatibility fixes documented in
  `docs/large_resources.md` (two dataclass defaults, IPA point-projection key
  remap, and an `openfold` path that does not shadow `scripts/`).

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
