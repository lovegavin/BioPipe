# Polygenic score harmonisation and scoring (PGS000297 subset)

## Data

| Input | Source | Size | SHA-256 |
|---|---|---|---|
| `chr22_prs.vcf.gz` | 1000 Genomes phase 3 chr22 (EBI), 25 regions (+/-150 kb around PGS000297 chr22 sites), 50 samples | 5,672,930 B | `293c63f8dd89f5e37ef946c48f1662a2aa3598c85497c0980fb438653b2d0cd2` |
| `PGS000297.txt.gz` | PGS Catalog GRS3290_Height (GRCh37), 3,290 weights, 37 on chr22 | 49,501 B | `5c06a400efaedae89d8e526924fe2af315b481ea73bb1ad8ab23b935b4bc5e41` |

The genotype file keeps the 50 samples carried by the earlier 1000 Genomes
routes (HG00096, HG00097, ...), so scores can be compared across routes.
Only the chr22 weights of PGS000297 are present; these scores are therefore a
chr22-only subset of the full-genome score and are not comparable to published
GRS3290 values.

## Route

```
genotypes (VcfReader) ─┐
genotypes_file (VcfFileReader) ─┤ prs_harmonize ─ export prs_harmonized.csv
weights (TsvFileReader) ────────┘        │
                                         ├─ prs_af_filter ─ export prs_filtered.csv
                                         ├─ prs_ld_clump  ─ export prs_clumped.csv
                                         └─ prs (existing) ─ export prs_scores.csv
```

`prs` is the existing `operon-genetics` scoring operator; it assumes dosages
and weights already refer to the same effect allele. `prs_harmonize` supplies
that contract by matching PGS rows to VCF records (rsID first, then
chrom:pos), flipping the sign when the effect allele is the reference allele,
and reporting ambiguous/absent rows instead of guessing.

## Results

| Step | Outcome |
|---|---|
| `prs_harmonize` | 37/37 weights placed: 24 matched, 13 flipped, 0 ambiguous, 0 absent |
| `prs_af_filter` | 37/37 kept; minimum MAF 0.02, maximum missing rate 0.0 |
| `prs_ld_clump` | 37/37 kept; largest within-100 kb r2 0.0257 |
| `prs` | 50 samples; score min 0.038704, max 0.278134, mean 0.149621; 37 variants each |

Wall time on WSL is about 2 min, dominated by the first VCF decode
(291,205 variants x 50 samples).

## Independent checks

| Check | Implementation | Result |
|---|---|---|
| Scores | independent NumPy dosage x weight | 50/50 samples, max abs 7.35e-09 (engine stores float32) |
| Scores | `plink2 --score` on the same weights | max abs 3.47e-07 (six-decimal score output) |
| Allele alignment | independent PGS/VCF parser | 0 sign errors, counts 24 matched / 13 flipped |
| MAF filter | independent dosage computation | 37/37 kept, min MAF 0.02 |
| Clumping | pairwise r2 inside 100 kb windows | 0 violations, max r2 0.0257 |

## Limits

- Only chr22 weights are available here; the full PGS000297 score spans the
  autosomes and cannot be reproduced from this subset.
- `prs` sums dosage x weight and treats missing dosages as zero, while
  `plink2 --score` imputes the mean; the two agree here because every call is
  present.
- Alignment is based on rsID or chrom:pos plus REF/ALT identity; strand flips
  without allele evidence are reported as `ambiguous`, never guessed.
- LD pruning uses the genotype dosages in this file and a 100 kb window; it is
  not a substitute for a population-specific reference panel.
