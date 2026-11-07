# Minibinder and VHH design route

This note records what Operon can do today for minibinder and VHH
(nanobody) design, which operators implement each step, and what is still a
roadmap item. It is written against the v1.53.1 operator library and is meant
to be revised as the library grows.

## The loop

1. **Target preparation.** `PdbReader` (12 columns, including `bfactor`) or
   `PdbqtReader` for docking inputs. Predicted structures come from
   `colabfold_predict` or `esmfold_predict`, and their confidence is read with
   `structure_plddt_profile` and `structure_pae_summary`.
2. **Interface description.** `structure_interface_core` (SASA-based core and
   rim residues), `interface_bsa`, `interface_contact_map`,
   `interface_hotspots`, `interface_hbond_network`,
   `interface_hydrophobic_patch`, `interface_distance_histogram`,
   `minibinder_interface` (per-residue contact counts and minimum distances).
3. **Epitope selection.** `proteinmpnn_hotspot_masked_design` turns the hottest
   interface residues into the only designable positions;
   `proteinmpnn_masked_interface_design` masks one side of a complex and scores
   the result with `proteinmpnn_masked_interface_score`.
4. **Backbone source.** Three options are supported: an existing VHH or
   scaffold structure, `rfdiffusion_design` (official RFdiffusion runner), or a
   binder model predicted from a designed sequence with ColabFold/ESMFold.
5. **Sequence design.** `proteinmpnn_design` and its 22 siblings (tied, omit,
   bias, temperature ladder, multi-model consensus, ensemble score, perplexity,
   probability profile, noise robustness, native recovery scan),
   `ligandmpnn_design`/`ligandmpnn_active_site_design` for ligand-aware
   contexts, and `esm_if_design`/`esm_if_redesign`/`esm_if_interface_redesign`
   for structure-conditioned sequence design.
6. **Developability triage.** `antibody_developability`,
   `antibody_cdr_physchem`, `antibody_cdr_hydrophobicity`,
   `antibody_cdr_length_profile`, `antibody_cdr_motifs`,
   `sequence_liability_scan` (deamidation, isomerisation, oxidation,
   N-glycosylation, pyroglutamate), `sequence_complexity`,
   `sequence_signal_peptide_v2`, `structure_glycosylation_sites`.
7. **Humanisation and numbering.** `antibody_cdr_kabat`,
   `antibody_numbering_kabat`, `antibody_numbering_imgt`,
   `vhh_humanization_score` (framework mismatches against IGHV3-23/IGHJ4),
   `vhh_humanization_mutations` (residues to revert), `structure_paratope_predict`.
8. **Structure re-check.** Re-predict each design (`colabfold_predict`,
   `esmfold_predict`, Boltz/AF2 through their own runners), then compare docked
   or predicted poses with `structure_ligand_pose_rmsd` and `vina_pose_rmsd`.
9. **Docking.** `ligand_pdbqt_prepare` (RDKit → PDBQT), `vina_dock` (single
   ligand), `vina_dock_batch` (library), `vina_pose_cluster`.
10. **Triage.** `proteinmpnn_design_cluster`, `rdkit_scaffold_diversity`,
    `esm_embedding_outlier_scan`, `esm_embedding_linear_probe`/`mlp_probe`
    (design-set classifiers), `structure_disorder_profile`.

## Modality: neutral, antagonist, agonist

Operon can represent a binder *class* only through the target conformation
that the user supplies. Neutral blockers are the straightforward case: mask the
receptor-binding site, design the interface, and filter on interface shape
complementarity and developability. Antagonists are modelled as binders to the
inactive-state structure with the orthosteric or allosteric surface masked.
Agonists require the active-state conformation and, in practice, an explicit
check that binding does not clash with the activation pathway, which Operon
cannot model today. There is no built-in state library, no functional assay and
no efficacy predictor; the class label is a workflow convention, not a property
the library can verify. `structure_paratope_predict` and the interface
statistics are the only current evidence.

## pH dependence

Not implemented. Today's scoring (ProteinMPNN likelihood, SASA, Vina affinity,
hydrogen bonds) is computed at a single fixed protonation state. A production
loop needs (a) protonation-state assignment at a target pH (PROPKA or a
constant-pH model), (b) pH-dependent interface terms (charge–charge and
hydrogen-bond penalties keyed to the protonation fractions), and (c) structure
ensembles at several pH values with a stability margin. `structure_hbonds`,
`structure_salt_bridges`, `structure_metal_coordination`,
`sequence_liability_scan` and `structure_ligand_pose_rmsd` are the pieces the
future operator would compose; none of them currently takes a pH parameter.

## Coverage summary

Readers: PDB, PDBQT, mmCIF-related paths, FASTA, CSV and the usual tabular
formats; all 101 Readers are registered by extension and dispatched with
`pick_reader(...).implementation()`.

Operators: 23 ProteinMPNN, 4 LigandMPNN, 21 ESM/ESM-IF, 10 antibody CDR, 2 VHH
humanisation, 13 interface, 4 docking, 39 structure, 28 RDKit, plus
RFdiffusion, ColabFold, ESMFold and the resource preflight.

Missing for a complete design stack: a packaged end-to-end route example, a
closed design → predict → filter loop with automatic iteration, an affinity
model beyond Vina and MPNN likelihoods, state-specific agonism, pH scoring,
and any wet-lab feedback.

Platform-level comparison and economic assessment:
[competitive landscape](competitive_landscape.md#platform-layer-assessment).
