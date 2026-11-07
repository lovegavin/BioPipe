# Operon Operator Library v3.0.1

Patch release on top of **Operon Operator Library v3.0.0**. No new
operators, no protocol change, no `export_results` contract change. This
release ships the fixes and evidence from the full 3.x verification campaign.

## Fixes

- **Structure interface** — third-party chain burial is no longer counted in a
  two-chain interface. For 1MEL A–L the reported interface drops from 54 to 46
  residues and ΔSASA from 2,034.31 Å² to 1,669.157 Å², matching the BSA value.
- **DSSP segments** — the parser now uses fixed DSSP columns; statistics rows
  and BP1 are no longer mistaken for chains. 1MEL now yields 187 segments over
  518 residues, matching the mkdssp oracle exactly.
- **Native export** — `ligand_pdbqt_flexible` now registers its PDBQT result
  file, completing 16/16 native producers.
- **Vina batch** — ligands with the same file stem no longer overwrite each
  other; output names use the unique label.
- **Vina Python** — default seed is 42, so repeated docking runs are
  reproducible.
- **Assembly stats** — QUAST is launched directly when its shebang is usable,
  preserving the conda environment (`ModuleNotFoundError: quast_libs` on POSIX);
  `.py` entry points always run with the current interpreter on Windows, fixing
  `OSError: [WinError 193]`.
- **antiSMASH** — genes present as both `gene` and `CDS` features are counted
  once.
- **ColabFold** — scores are copied into the task artifact directory instead of
  pointing at a deleted temporary directory.
- **Protein properties** — molecular weight no longer adds a water molecule per
  residue; VHH 132 aa is 13,877.23 Da (5.3 ppm from ProtParam) instead of
  16,255.25 Da.
- **ViennaRNA fold/cofold/duplex** — ensemble output is enabled and parsed,
  cofold structures with commas are accepted, and the duplex energy range has a
  0.1 kcal/mol floor instead of silently producing no records.
- **GTF annotation** — `gff_feature_stats`, `gene_structure` and
  `annotation_gaps` accept GTF as well as GFF3 through the annotation role
  aliases.

## Verification

- 717 operators / 101 Readers / 7 packages / 24 routes, registry `errors []`.
- All 24 builtin routes checked and executed; 16/16 native producers exported
  with byte-identical SHA-256.
- External oracles: QUAST, Biopython, mkdssp, tmtools, ViennaRNA,
  ProtParam, statsmodels/SciPy, scanpy and scikit-bio.
- Windows 3.12.10: frozen-route pytest set 50 passed / 7 skipped; the new
  regression files 11 passed / 4 skipped.
- Full suite: see `docs/verification/library-3.0.0-full.md`.

## Compatibility

- Minimum application: **2.4.1**; built and verified against the published
  2.4.1 application wheel.
- Protocol: v3, unchanged.
- Application/backend version remains 3.0.0; this is an operator-library-only
  patch.
