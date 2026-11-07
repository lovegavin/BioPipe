# Hard-capability status

The library policy (see `extension_policy.md`) limits new work to capabilities
that are hard to implement or verify and analytically important. This page
records the current state of that queue, including what is blocked and why, so
nobody re-reports a blocked item as delivered.

## Verified

| Capability | Evidence |
| --- | --- |
| `foldseek_search` | Real run: Foldseek 10-941cd33 static binary + a local database built with `foldseek createdb` from two fixtures; 1MEL query returned 5 hits, top self-hit `alntmscore 1.008`. Real-run test activates with `OPERON_FOLDSEEK_BIN`/`OPERON_FOLDSEEK_DB`. |
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

- `structure_dockq`: own CAPRI DockQ implementation (native contact fraction at
  5 A, interface backbone iRMSD at 10 A, receptor-superposed ligand RMSD,
  DockQ = (Fnat + 1/(1+(iRMSD/1.5)^2) + 1/(1+(LRMSD/8.5)^2))/3). Validated
  against the official `DockQ` CLI on 1MEL: identical complex gives DockQ
  **1.000**; a +2 A/+1 A rigid shift of chains A/B gives ours **0.8145**
  (fnat 0.75, iRMSD 0.858, LRMSD 2.150) versus official AL **0.8040**
  (fnat 0.716, iRMSD 0.843, LRMSD 2.236), a 0.0105 gap that comes from the
  heavy-atom contact set.

- `structure_lddt`: own per-residue lDDT (15 A inclusion radius, 0.5/1/2/4 A
  thresholds, C-alpha atoms) validated against OpenFold's differentiable
  `lddt()` implementation on 1MEL: copies A vs B mean **0.9673 both** (max
  per-residue difference 0.000000), A plus 1 A Gaussian noise gives **0.6538
  both**, and A vs A gives **1.0000 both**.

- `structure_openmm_md_rmsf`: short implicit-solvent MD (Amber14 + GB-Neck2,
  LangevinMiddle, 2 fs) with per-residue C-alpha RMSF validated against
  `mdtraj.rmsf` on the same trajectories. Real run on 1MEL chain A (1881
  particles, 2000 steps / 4 ps, 20 frames): mean RMSF **0.0477 nm** (min
  0.0241, max 0.1131), radius of gyration 1.398-1.417 nm (mean 1.408); the
  most flexible residues are the CDR loops PRO41/GLY42 (0.113/0.111 nm) and
  the terminal SER133, run time **156 s** on CPU. The oracle test agrees with
  mdtraj to 1.6e-7 nm.

- `structure_ligand_pose_qc`: wraps the official PoseBusters suite (0.6.5,
  `dock` and `mol` configs). Real runs on a synthetic aspirin complex: 22
  checks; a far pose passes bond lengths and volume overlap but fails
  `minimum_distance_to_protein` (the dock config expects a pocket pose), a
  superimposed pose additionally fails `volume_overlap_with_protein`, and a
  stretched atom fails `all_atoms_connected` and `internal_steric_clash`.
  Bond-length checks only fire when the ligand block is chemically
  parseable (the operator prefers an RDKit SDF round trip and falls back to
  the raw PDB).

- `structure_pocket_detect`: wraps fpocket 4.0, built from source at
  `~/tools/fpocket` (GitHub `Discngine/fpocket`, `make`; binary
  `bin/fpocket`). Real run on 1MEL (heavy atoms rewritten, 21 pockets
  detected, 5 kept): top score **0.317**, druggability 0.005, volume
  517 A^3, 52 alpha spheres, 17 lining residues, 0.7 s; another cavity
  reaches druggability **0.405** with volume 634 A^3. Pocket parsing
  distinguishes `Volume :` from the `Volume score:` line.

- `sequence_rna_fold`: wraps ViennaRNA 2.5.1 (`apt install vienna-rna`,
  `/usr/bin/RNAfold`) for minimum-free-energy RNA secondary structure.
  Real runs: yeast tRNA-Phe (76 nt) folds to a cloverleaf-like structure
  with MFE **-22.40 kcal/mol** and 21 base pairs, byte-identical to the
  direct CLI output; the hairpin `GGGAAACCC` gives -1.20 kcal/mol and
  `(((....)))`; two sequences fold in 0.01 s. T is normalised to U and
  non-nucleotide characters are rejected.

- `sequence_rna_ensemble`: runs `RNAfold -p` (ViennaRNA 2.5.1) and reports
  the MFE energy, ensemble free energy, MEA energy and diversity, MFE
  frequency and ensemble diversity. Real run: yeast tRNA-Phe 76 nt gives
  MFE **-22.40**, ensemble **-24.13**, MEA **-3.01** (d=16.21), MFE
  frequency **0.0607** and ensemble diversity **23.38**, exactly matching
  the CLI frequency line; 0.01 s per sequence.

- `vina_dock_python`: drives the official AutoDock Vina Python engine
  (`vina 1.2.7`). The operator writes a rigid PDBQT receptor from the atom
  Form (AD4 atom types, zero charges), uses the prepared ligand PDBQT, and
  reports every pose's scoring terms. Real run: aspirin into 1MEL, box at
  the ligand centroid, exhaustiveness 8, 5 modes in **2.0 s**, best
  affinity **-3.0 kcal/mol** (poses -3.00, -2.98, -2.84, -2.83, -2.81).
  The ligand preparer now emits `ROOT`/`ENDROOT`, which Vina requires.

- `ligand_pdbqt_flexible`: builds a ROOT/BRANCH/ENDBRANCH torsion tree from
  RDKit rotatable single bonds (both atoms heavy with degree >= 2, acyclic,
  amide bonds excluded) and sets TORSDOF accordingly. Verified against the
  Vina engine: aspirin (3 torsions, 3 BRANCH blocks) docks flexibly into
  1MEL with best affinity **-2.43 kcal/mol** (rigid ligand -3.00), torsion
  penalty 0.43, internal strain -0.37. Note that Vina 1.2.7 writes and
  expects `BRANCH <parent> <child>` while ADT documentation states the
  reverse; the operator follows the Vina convention.

- `structure_pdbqt_flexible_receptor` + `vina_dock_python(flex_path=...)`:
  splits the receptor into a rigid PDBQT and `BEGIN_RES` flex blocks
  (ROOT = CB, branches along side-chain torsions, no TORSDOF inside
  BEGIN_RES). Real run on 1MEL with VAL A:2 flexible (3 side-chain atoms,
  one chi torsion): Vina accepts the pair and docks aspirin at
  **-2.36 kcal/mol** (rigid receptor -2.43), torsion penalty 0.41.
  Candidate residues: 402 of 1MEL side chains are selectable.

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
   superfamily assignment. Test 253 now clears `OPERON_PFAM_HMM` for the
   validation branch so the suite is environment-neutral.

Until then these stay documented as gated; no easy substitute operator is added
to fill a batch.

## v1.86.0 structure_md_ss_occupancy (verified)

- mkdssp 4.2.2 on MD frames written from the OpenMM trajectory; per-residue
  helix/strand/coil occupancy and dominant state; tests 4 passed; 675/101.

## v1.87.0 sequence_rna_duplex (verified)

- ViennaRNA RNAduplex wrapper; parser checked against the CLI; 4 tests passed;
  676 operators / 101 Readers.

## v1.88.0 sequence_rna_cofold (verified)

- ViennaRNA RNAcofold -p -c wrapper; MFE, binding energy and five-species
  equilibrium concentrations; 3 tests passed; 677 operators / 101 Readers.

## v1.89.0 structure_md_contact_occupancy (verified)

- Heavy-atom residue contact occupancies across MD frames; brute-force
  distance cross-check; 4 tests passed; 678 operators / 101 Readers.

## v1.90.0 structure_md_salt_bridge_occupancy (verified)

- Acidic/basic side-chain pair occupancies across MD frames; 4 tests
  passed; 679 operators / 101 Readers.

## v1.91.0 structure_md_hbond_occupancy (verified)

- Donor-H...acceptor geometry across MD frames; 1MEL real check (4074 atoms,
  132 bonds at >= 99%); 4 tests passed; 680 operators / 101 Readers.

## v1.92.0 structure_md_sasa_occupancy (verified)

- Per-residue Shrake-Rupley SASA across MD frames; analytic single-atom
  oracle 120.76 A^2; 1MEL real check (551 residues, mean 39.8 A^2);
  5 tests passed; 681 operators / 101 Readers.

## v1.93.0 structure_md_dihedral_occupancy (verified)

- Backbone phi/psi and coarse Ramachandran occupancy across MD frames;
  mdtraj angle cross-check; 1MEL (132 residues, alpha 0.12, beta 0.57);
  5 tests passed; 682 operators / 101 Readers.

## v1.94.0 structure_ligand_redock_qc (verified)

- PoseBusters redock validation; 3PTB real check (shifted pose rmsd 3.0 /
  fail, identity rmsd 0.0 / pass); 3 tests passed; 683 operators / 101 Readers.

## v1.95.0 structure_md_ligand_rmsd (verified)

- Receptor-superposed ligand displacement across MD frames; 3PTB real check
  (1.0 A shift -> 1.000 A); 5 tests passed; 684 operators / 101 Readers.

## prodigal_genes (verified, 2.6.3)

- apt-installed Prodigal 2.6.3; real run on phage lambda (48 502 bp):
  61 CDS, first CDS 191-736 (+), identical to the CLI GFF output.
- Real test gated by OPERON_PRODIGAL_REAL=1 in tests/test_extension252.py.

## hmmer_domains (verified, Pfam-A)

- Pfam-A.hmm (418 MB gz, 2.2 GB unpacked) pressed with hmmpress; real scan
  of chicken lysozyme returned 3 domains, top hit 'Lys' with full score 166
  in 0.7 s; real test gated by OPERON_PFAM_HMM.

## esm3_embedding (verified)

- ESM-3 open 1.40 B model loaded from the hf-mirror cache; per-residue
  embeddings (1, 14, 1536) in 6.0 s on CPU; real test gated by
  OPERON_ESM3_REAL; 685 operators / 101 Readers.

## esm3_inverse_folding (verified)

- ESM-3 open model, coordinates-only generation on 1MEL chain A (132 res,
  10 steps, CPU): recovery 0.788 in 20.2 s; real test gated by
  OPERON_ESM3_REAL; 686 operators / 101 Readers.

## esm3_fold (verified)

- ESM-3 structure track on 1MEL chain A (132 res, 10 steps, CPU): 527 atoms,
  pLDDT 0.900, pTM 0.836, CA RMSD 1.97 A vs crystal, 21 s; real test gated
  by OPERON_ESM3_REAL; 687 operators / 101 Readers.

## Elastic network models (verified)

- GNM/ANM implemented in NumPy and cross-checked against ProDy on 1MEL chain A
  (132 CA): GNM MSF agreement 1e-5, ANM 1e-4; ANM 6 rigid-body zero modes;
  689 operators / 101 Readers.

## Open incompatibility: ESM-3 on the managed server runtime

ESM-3 now runs through the dedicated-environment bridge
(`operon.env_worker` + `proxy_step`): the runner never imports the model in the
host interpreter, and `tests/test_environments.py` covers the bridge. A real
generation was verified locally through the bridge
(`MKTAYIAKQR________` + 2 steps -> `MKTAYIAKQRLLLIALTL`, 18 residues).

`esm3_sequence_generation` requires Python >= 3.12. On the CentOS-7 class
server the newest installable torch is 2.6.0 (manylinux_2_17), so the bridge
pins **Python 3.12 + torch 2.6.0 + ESM 3.2.2** there; ESM 3.4's `torch>=2.11`
pin is not satisfiable on that OS.
The managed server environment is Python 3.11 with torch 2.6, so the operator
cannot share it. AntiFold had the same class of conflict and is now solved with
a dedicated interpreter (`resources.environment = "antifold"`, resolved by
`operon.environments`). ESM-3 needs the same mechanism plus a subprocess
execution bridge for in-process operators; until that ships the dependency probe
correctly reports it as unavailable instead of hiding it behind a warning.
