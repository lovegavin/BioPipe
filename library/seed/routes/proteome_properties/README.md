# E. coli proteome composition, extinction and stability

Protein quality-control metrics over the *E. coli* K-12 proteome: amino-acid
composition, A280 molar extinction coefficients, and the Guruprasad instability
index.

## Data

| File | Size | SHA-256 |
| --- | --- | --- |
| `input/protein.faa` | 1,750,878 B | `9b8d21ea8ea5180bd9a96d7895dba9b5789002f43c6f421f2a7cdd1b141aa129` |

Source: NCBI RefSeq *Escherichia coli* K-12 MG1655 protein FASTA
(`GCF_000005845.2`, 4,300 proteins). The file also contains three proteins with
selenocysteine (`U`): `NP_415991.1`, `NP_418330.1`, `NP_418503.1`.

## Steps

1. `protein_composition` — 20 standard residues counted per protein.
2. `export_results` — `protein_composition.csv`.
3. `protein_extinction` — `5500*W + 1490*Y`, plus `125 * (C // 2)` for cystines.
4. `export_results` — `protein_extinction.csv`.
5. `protein_instability` — Guruprasad instability index, stable at `<= 40`.
6. `export_results` — `protein_instability.csv`.

## Results

| Metric | Value |
| --- | --- |
| Proteins in FASTA | 4,300 |
| Proteins analysed | 4,297 |
| Skipped (non-standard residues) | 3 |
| Total residues | 1,327,290 |
| Mean length | 308.8876 |
| Unstable proteins (index > 40) | 1,692 |

| Export | Size | MD5 |
| --- | --- | --- |
| `protein_composition.csv` | 449,053 B | `a63c9d5f40104df804766e5d6bf177b5` |
| `protein_extinction.csv` | 203,886 B | `3f3e7dc9c573a3a70a5cd1937fd70e97` |
| `protein_instability.csv` | 152,233 B | `924d3cac101e252a2e6e42575b622f7f` |

WSL run: 6/6 steps, `total_elapsed` 0.245 s, wall 3.04 s, MaxRSS 121,036 KB.

## Oracles

| Implementation | Scope | Result |
| --- | --- | --- |
| Biopython `ProtParam` | all 4,297 rows | composition 0, A280 max 2.37e-7, instability max 3.79e-6 |
| EMBOSS `pepstats` 6.6.0.0 | first 300 proteins | residue counts, reduced and cystine extinction: 0 mismatches |

## Limitations

- The FASTA reader encodes residues outside the 20 standard amino acids as `N`.
  The operators therefore read the reader's raw `info.sequences` and skip
  proteins that contain non-standard residues instead of silently counting them
  as asparagine.
- A280 of a 1 mg/ml solution follows the average-residue molecular weight; EMBOSS
  reports monoisotopic-based values, so compare the molar coefficients, not the
  1 mg/ml column.
- Instability index is defined only for the 20 standard residues.
