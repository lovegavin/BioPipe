# Structure validation: missing residues, alternate conformers and cis peptides

This route exercises three coordinate-level structure checks on public PDB
entries.  Every check is a read-only analysis of the atoms that are actually
present in the file; nothing is rebuilt from a tensor and no coordinates are
written back.

## Inputs

| Source | PDB | Size | Why it is used |
| --- | --- | --- | --- |
| `structure_1mel` | [1MEL](https://files.rcsb.org/download/1MEL.pdb) | 353 KiB | Camelid VHH dimer with contiguous numbering; gap negative control and cis-peptide positive control (A30–A31, B30–B31) |
| `structure_3di3` | [3DI3](https://files.rcsb.org/download/3DI3.pdb) | 250 KiB | IL-7 / IL-7Rα complex; one internal gap A:99–121 (23 residues) |
| `structure_2vb1` | [2VB1](https://files.rcsb.org/download/2VB1.pdb) | 437 KiB | 0.65 Å lysozyme; 1,440 atoms across 4 alternate-location labels and 49 residues with alternates |

All three files were downloaded from RCSB on 2026-11-07.  Copies are stored in
`workdir/b5_route/input/` and are not committed to the repository.

## Steps

1. `structure_missing_residues` on 1MEL → `missing_1mel`
2. `export_results` → `missing_residues_1mel.csv`
3. `structure_missing_residues` on 3DI3 → `missing_3di3`
4. `export_results` → `missing_residues_3di3.csv`
5. `structure_altloc_inventory` on 2VB1 → `altlocs_2vb1`
6. `export_results` → `altloc_inventory_2vb1.csv`
7. `structure_cis_peptides` on 1MEL → `cis_1mel`
8. `export_results` → `cis_peptides_1mel.csv`

## Oracles

| Check | Oracle (version) | Measured agreement |
| --- | --- | --- |
| Missing residue ranges | gemmi 0.6.5 residue numbering + RCSB REMARK 465 | 3DI3 A:99-121, 23 missing - identical; every missing residue is declared in REMARK 465; 1MEL and 2VB1 report zero internal gaps |
| Alternate conformers | gemmi 0.6.5 altloc inventory | labels _, A, B, C; max abs difference 1.5e-8 over atom counts, residue counts and occupancy extremes |
| Cis peptides | gemmi 0.6.5 calculate_dihedral (converted from radians), abs(omega) <= 30 degrees | 514 bonds; 2 cis (A:30-31, B:30-31) on both sides; max abs omega difference 7.6e-6 degrees; 0 label or cis-flag mismatches |

Raw comparison output is kept with the development evidence and is not part
of the installed library.

## Limits

- Only internal numbering gaps are visible.  Terminal truncation cannot be
  inferred from a coordinate file because absent residues leave no trace.
- Non-standard residues and insertion codes are reported by their PDB numbering;
  a chain that restarts numbering is reported as one gap.
- Alternate conformers are reported as they appear in the file.  A structure
  without `altloc` identifiers yields a single blank row, which is the correct
  result for that file (it does not prove the crystal had no disorder).
- Cis-peptide detection needs a complete `CA`, `C`, `N`, `CA` backbone on both
  sides of the bond; bonds across a gap or with missing backbone atoms are
  skipped and counted in `n_skipped`.
