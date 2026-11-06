# MSA analysis route

Four operators that summarise and clean a multiple sequence alignment without
calling an external aligner: `msa_column_stats`, `msa_consensus`,
`msa_identity_matrix` and `msa_trim`.

## Inputs

| Source | File | Size | SHA-256 |
| --- | --- | --- | --- |
| `protein_msa` | `input/pf00069_aligned.fasta` | 16,491 B | `b6e130f45be1e63a1c6bda22fcdce7641781a1b8a2dbbd056a55df344f95228f` |
| `rna_msa` | `input/ssu_aligned.fasta` | 48,899 B | `6df770ce70b0e6e6dac180266929c5f61d2929cb93c846fc4809d18945772c44` |

`pf00069_aligned.fasta` is the Pfam PF00069 (protein kinase domain) seed
alignment downloaded from the InterPro API
(`https://www.ebi.ac.uk/interpro/wwwapi/entry/pfam/PF00069/?annotation=alignment:seed`,
36,601 B Stockholm, 37 sequences x 419 columns) and converted to FASTA with the
gap character preserved.

`ssu_aligned.fasta` is the 24-sequence subset of the Rfam RF00177
(SSU_rRNA_bacteria) seed alignment used by the phylogeny route: alignment length
1,980, gap fraction below 0.5, taken at an even stride from the 99 Rfam
sequences.

## Steps

1. `msa_column_stats` on the protein alignment, exported to CSV.
2. `msa_consensus` on the protein alignment (gap > 0.5 or major fraction < 0.4
   becomes `X`), exported to FASTA.
3. `msa_identity_matrix` on the protein alignment (identity over columns where
   both sequences have a residue), exported to CSV.
4. `msa_trim` on the protein alignment (columns with gap fraction <= 0.3, rows
   with at least 70% called residues), exported to FASTA.
5. `msa_column_stats` and `msa_consensus` on the RNA alignment, exported to CSV
   and FASTA.

## Results (WSL, python 3.12)

The route completes 12/12 steps in 0.80 s with a peak RSS of 97,212 KB.

| Output | Bytes | MD5 |
| --- | --- | --- |
| `msa_columns_pf00069.csv` | 27,155 | `fb4b7dada33209ea3b11723a8e95d899` |
| `msa_columns_rfam.csv` | 86,775 | `9a093e24f7f49f12ea635fb18141b065` |
| `msa_consensus_pf00069.fasta` | 436 | `c7ac6457c1fafe642df9a14c82018230` |
| `msa_consensus_rfam.fasta` | 2,016 | `8a0724cc3c95b76ea156054583a70d8c` |
| `msa_identity_pf00069.csv` | 26,756 | `7b17509334b1a8743d31a07da1e462a6` |
| `msa_trimmed_pf00069.fasta` | 10,016 | `58029201417399d72ef478f6920da845` |

The protein consensus is 419 characters, 309 of them ambiguous; the RNA
consensus is 1,980 characters, 526 of them ambiguous. Trimming keeps 246 of the
419 protein columns and all 37 sequences.

## Oracles

Both oracles are independent of the operator code and of each other:

| Oracle | Implementation | Result |
| --- | --- | --- |
| Pure Python | `workdir/b18_oracle.py`, hand-written FASTA/CSV parsing | max absolute difference 0.0 for gap fraction, entropy, conservation and major fraction on both alignments; consensus identical; identity matrix 0.0; trimmed alignment identical (246 columns, 37 rows) |
| Base R 4.3.3 | `workdir/b18_oracle.R`, no R packages | same four per-column statistics 0.0 on both alignments; consensus identical (309 `X`, 526 `N`); identity matrix 0.0 |

## Limitations

- The operators consume an existing alignment; they never align sequences.
- `msa_trim` removes whole columns only; it does not remove all-gap columns from
  a single sequence independently.
- Consensus thresholds are per-run parameters; the defaults (0.5 gap, 0.4 major
  fraction) are not a biological recommendation.
- Identity counts only columns where both sequences carry a residue, so pairs
  with few comparable columns can report a high identity from a short overlap.
- The alphabet is inferred once per alignment (`dna`, `rna`, `protein`); an
  alignment mixing nucleotide and protein characters is rejected.
