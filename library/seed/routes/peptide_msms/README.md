# Peptide MS/MS fragment, isotope and modification QC

This route digests a small real proteome and derives three mass-spectrometry
views that are otherwise absent from the operator catalogue: theoretical
fragment ions, isotope envelopes and modification-aware peptide masses.

## Data

| File | Bytes | SHA256 |
| --- | --- | --- |
| `proteins.faa` (first 20 proteins of the E. coli K-12 proteome) | see `meta.json` | see `meta.json` |

The FASTA is a prefix of the UniProt reference proteome used by the
proteomics QC route; no synthetic sequences are involved.

## Steps

1. `protein_digest` (trypsin, no missed cleavages, 8-20 aa)
2. `peptide_fragment_ions` (b/y ions, charge 1-2)
3. `export_results` (CSV)
4. `peptide_modified_mass` (fixed carbamidomethyl cysteine, +57.02146372)
5. `export_results` (CSV)
6. `peptide_isotope_envelope` (4 peaks, charge 1)
7. `export_results` (CSV)

## Results (WSL, 2026-11-07)

- 178 peptides from 20 proteins.
- 8,264 fragment ions; 712 envelope peaks; 178 modified masses.
- Route elapsed 0.30 s.

## Oracles

| Quantity | Reference | Comparison |
| --- | --- | --- |
| b/y fragment m/z | pyteomics 4.7.5 `fragment_series` | 8,264 compared, max abs 5.36e-7 |
| modified mass | molmass 2026.11.1 atomic formula (+C2H3NO per cysteine) | 178 compared, max abs 7.07e-8 |
| isotope envelope | molmass `Formula.spectrum()` | 712 compared, max abs m/z 1.19e-4, fraction 1.35e-2 |

`pyteomics.fast_mass` silently ignores `fixed_mods`, so the modification
oracle composes the elemental formula from `pyteomics.std_aa_comp` and adds
C2H3NO per cysteine; it is an independent implementation from the operator's
residue mass table.

## Limitations

- b/y ions only; a/x/c/z ions and neutral losses are not modelled.
- Isotope envelopes report the first consecutive nominal-mass peaks starting
  at the monoisotopic peak; peaks are binned by nominal mass.
- Fixed modifications are limited to residue-level mass shifts in
  `RESIDUE:MASS` form.
