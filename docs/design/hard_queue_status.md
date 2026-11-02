# Hard-capability queue status

This page records which hard capabilities are verified end to end, which are
wrapper-aligned but resource-gated, and which are blocked by missing tools in
the current environment. It complements `hard_capability_status.md`, which
tracks the individual operator evidence, and `extension_policy.md`, which
defines what is accepted into the core library.

Snapshot: **671 operators / 101 Readers** (v1.82.0).

## Verified end to end

| Capability | Implementation | Evidence |
| --- | --- | --- |
| Structure prediction (Boltz) | `boltz_predict` | Boltz-1 peptide pLDDT 0.885, Boltz-2 peptide+ligand affinity 1.906 |
| Binding affinity | `boltz_affinity_summary` | real `affinity_aff.json`, operator reproduces the table |
| Structure prediction (ESMFold) | `esmfold_predict` | facebook esmfold_v1 8.4 GB, VHH mean pLDDT 0.846 |
| Structure prediction (OpenFold) | `openfold_predict` | finetuning_ptm_2 weights, 36.8 s CPU, pLDDT 68.7 |
| Inverse folding (anti-body) | `antifold_design` | OPIG model.pt 566 MB, CDR-focused designs |
| Structural search | `foldseek_search` | Foldseek 10-941cd33, local DB, 5 hits on 1MEL |
| Pocket detection | `structure_pocket_detect` | fpocket 4.0 built from source, 21 pockets on 1MEL |
| MD flexibility | `structure_openmm_md_rmsf` | OpenMM GB-Neck2, RMSF agrees with mdtraj to 1.6e-7 nm |
| MM/GBSA and alanine scan | `interface_mmgbsa_delta`, `interface_alanine_scan` | OpenMM force-group decomposition, hand-checked |
| pKa and protonation | `structure_protonation_pka` | pdb2pqr/PROPKA, lysozyme charge relay reproduced |
| Pose validation | `structure_ligand_pose_qc` | PoseBusters 0.6.5, 22 checks per complex |
| RNA folding | `sequence_rna_fold`, `sequence_rna_ensemble` | ViennaRNA 2.5.1, tRNA-Phe MFE -22.40 kcal/mol |
| Structural metrics | `structure_tm_score`, `structure_lddt`, `structure_dockq` | tmtools, OpenFold `lddt`, DockQ CLI oracles |

## Resource-gated but honest

- `vina_dock_python`: verified end to end with the `vina` Python engine
  (see `hard_capability_status.md`); the CLI wrappers remain resource-gated.
- `vina_dock`, `vina_dock_batch`, `vina_pose_cluster`, `vina_pose_rmsd`:
  AutoDock Vina is **not installed** (`vina` missing from PATH). The wrappers
  are contract-tested with a runner double and report a clear error; installing
  Vina (binary or the `vina` Python package) is the unblock step.
- `ligandmpnn_*` side-chain packing: the LigandMPNN side-chain checkpoint is
  not present locally, so only the design/score checkpoints run.
- `proteinmpnn_*` variants: run against the official checkout and local
  weights; no missing resources.

## Blocked in this environment

1. **ESM-3** (`esm3-*`): the open weights are behind a gated Hugging Face
   repository; `huggingface.co` resolves to a blackholed IPv4 address and an
   IPv6 address with no WSL route. `hf-mirror.com` mirrors the Boltz and ESM
   checkpoints but not the gated ESM-3 release.
2. **AlphaFold2 / multimer inference**: OpenFold weights are present, but the
   full AlphaFold parameter bundle and the UniRef/Uniclust MSA databases are
   absent, and the download hosts are unreachable (same HF block). The
   `openfold_predict` operator therefore runs single-sequence mode only.
3. **gnina docking and OpenBabel conversions**: `gnina` and `obabel` are not
   installed and are not in the Ubuntu package set used here; no local
   alternative provides the same scoring/conversion authority.
4. **RNA local accessibility (`RNAplfold` unpaired profile)**: the packaged
   ViennaRNA 2.5.1 build writes only `_dp.ps` postscript and does not emit the
   `_lunp` unpaired-probability file, so an honest parser cannot be validated.
5. **Free-energy perturbation / rigorous binding free energy**: no local
   alchemical engine (OpenMM alone requires a full setup and reference
   implementations that are not available offline); results would be
   unverifiable.

## Policy

New capabilities are accepted into the core only when they are hard to
implement or hard to verify, analytically important, and provable against an
authoritative oracle or a real local run. Easy or niche operators stay out of
the library and are documented for on-demand extension, as recorded in
`extension_policy.md`.
