# BioPipe Operator Library v3.0.0

Backend version: 3.0.0 (operators 717, Readers 101).
Tag: `library-v3.0.0`. Minimum and build application: `3.0.0`.
Base library: `2026.11.5.2` (domain exports and GenBank Reader retained).

This is the coordinated operator-library release for BioPipe 3.0.0. It does not
add operators or writers; it makes the existing capability set exportable and
keeps `export_results` as the only output boundary.

## Native file registration

- Structure prediction: `boltz_predict`, `boltz_complex_confidence`,
  `colabfold_predict`, `openfold_predict`, `esmfold_predict`, `esm3_fold`.
- Assembly: `flye_assemble` (assembly FASTA).
- Docking and ligands: `vina_dock`, `vina_dock_python`, `vina_dock_batch`,
  `ligand_pdbqt_prepare`, `ligand_pdbqt_flexible`,
  `structure_pdbqt_flexible_receptor`.
- Packing: `ligandmpnn_side_chain_packing`.
- Existing `proteinmpnn_design` and `rfdiffusion_design` registrations are kept.

Each producer writes its final file under the task output directory and records
the file in `result_files`; `export_results` can then export it as `native`
without copying or rebuilding it.

## Sequence exports

- `_sequence_common.encode_sequences` records `info.sequences` on every sequence
  Form.
- `FastaReader` records the parsed sequences and declares the additive info field
  in its output contract.

## Fixed

- `sequence_liability_scan` exports the residue at each liability site instead of
  raising `KeyError: 'residue'`.
- `nmds` adapts its keyword arguments to the installed scikit-learn `MDS`
  signature.

## Unchanged

- No changes to `export_results`, protocol v3, operator IDs or parameter schemas in
  this release; the 2026.11.5.2 domain-export implementation is included unchanged.
- Frontend Studio 2.4.1.
- No new operators, Readers, writers or large-resource downloads.

## Validation

- 717 operators / 101 Readers / 7 packages / 24 routes, registry errors `[]`.
- Focused operator/export/viewer suites: 140 passed, 23 skipped.
- Export-contract suite: 28 passed.
- Full offline suite: **2857 passed, 222 skipped, 0 failed** (28m32s).
- Packaging group: 68 passed.
- Library release mechanics: [release standard](../library_release_standard.md).

## Limits

- `native`/`pdb`/`cif` export requires a producer file or a `FileArtifact`;
  uploaded PDB/FASTA bytes are not retained by the Reader.
- FASTA conversion requires `info.sequences`; table-only design summaries do not
  invent sequences.
- Optional real-model gates: ESM-IF tests skip when ESM-3 shadows `fair-esm` or
  `torch_scatter` is ABI-incompatible with torch; the DockQ oracle skips when its
  released CLI was built against NumPy 1.x.
