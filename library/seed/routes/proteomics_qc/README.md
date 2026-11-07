# Proteomics digest and coverage (proteomics_qc)

End-to-end peptide QC over a real bacterial proteome: digest every protein with
trypsin, compute monoisotopic peptide masses at charge 2, and measure how much
of each protein the peptide set covers.

## Data

| Input | Source | Size | sha256 |
| --- | --- | --- | --- |
| `protein.faa` | NCBI RefSeq `GCF_000005845.2` (E. coli K-12 MG1655) protein FASTA | 1,750,878 B, 4,300 proteins | `9b8d21ea8ea5180bd9a96d7895dba9b5789002f43c6f421f2a7cdd1b141aa129` |

The proteome uses the 20 standard residues plus three selenocysteine (`U`)
positions; the operators reject unsupported residues rather than guessing a
mass, and no peptide in this digest contains one (`skipped_unsupported = 0`).

## Steps

1. `protein_digest` — trypsin, `missed_cleavages = 0`, peptide length 6–50.
2. `export_results` — `protein_digest.csv`.
3. `peptide_mass` — charge 2, monoisotopic masses and m/z.
4. `export_results` — `peptide_mass.csv`.
5. `peptide_coverage` — per-protein covered residues over merged peptide spans.
6. `export_results` — `peptide_coverage.csv`.

## Results

| Metric | Value |
| --- | --- |
| Proteins | 4,300 |
| Peptides (length 6–50) | 72,399 |
| Unsupported-residue peptides skipped | 0 |
| Mass range at charge 2 (Da) | 474.2438 – 5,948.0255 |
| Proteins with at least one peptide | 4,289 / 4,300 |
| Mean protein coverage | 0.8152563387729529 |

Step timings on WSL: digest 0.4901 s, mass 0.3325 s, coverage 0.0541 s,
exports 0.2010 s, total 1.0777 s. Exports are 4,681,593 B, 4,041,263 B and
205,464 B respectively.

## Oracles

| Oracle | Scope | Result |
| --- | --- | --- |
| pyteomics `parser.xcleave(seq, "[KR](?!P)")` + `mass.calculate_mass` | peptide set, masses | 72,399 vs 72,399, zero one-sided peptides, max abs mass diff **3.64e-12** |
| EMBOSS `pepdigest` 6.6.0, `-menu 1 -mono Y -unfavoured Y` | cut sites, masses | every extra EMBOSS fragment is explained by a `K/R|P` cut (0 unexplained), 0 unexplained merges, max abs mass diff **6.22e-4** (EMBOSS prints three decimals) |
| EMBOSS `pepdigest` default (KRIFLP heuristic) | self-consistency | 88,397 fragments tile the unfavoured fragments with 0 violations |

EMBOSS applies two documented conventions that differ from the standard
trypsin rule used here (and by pyteomics): `-unfavoured Y` cuts after every
`K`/`R`, including `K/R|P`, while the default mode skips `K/R` followed by
`K`, `R`, `I`, `F`, `L` or `P`. The route therefore reports pyteomics as the
primary numeric oracle and uses EMBOSS to confirm that every extra fragment is
a `K/R|P` split (5,767 such sites in this proteome) rather than a disagreement
about peptide boundaries.

## Limits

- Standard trypsin semantics: no cut before proline; `missed_cleavages = 0`.
- Peptides outside 6–50 residues are filtered before mass and coverage.
- Coverage counts merged span overlap, not per-residue spectral evidence.
- `peptide_mass` supports charges 1–4 and the 20 standard residues plus `U`
  and `O`; any other residue is an error.
