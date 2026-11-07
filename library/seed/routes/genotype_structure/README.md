# Genotype structure (1000 Genomes chr22)

## Input data

| File | Size | SHA-256 | Content |
| --- | --- | --- | --- |
| `subset_snps.vcf.gz` | 541,728 B | `57c1870b83244ae3ba74880f89a1ef69b508bfecad50e8bc998e233a2d060c05` | 28,522 biallelic SNPs, 50 samples (1000 Genomes GBR panel), chr22 17,000,515-18,000,000 |

Derived from the 1000 Genomes chr22 query VCF used by batch 25 with
`bcftools view -m2 -M2 -v snps`. There is no missing genotype call. Only 4,388
of the 28,522 sites are polymorphic in these 50 samples; the remaining 24,134
sites are monomorphic and contribute a zero column to the standardised matrix.

## Steps

1. `genotype_pca` - sample scores and eigenvalues (`n_components = 5`).
2. `export_results` - `genotype_pca.csv`.
3. `genotype_grm` - genetic relationship matrix.
4. `export_results` - `genotype_grm.csv`.
5. `genotype_pca_loadings` - per-variant weights for each component.
6. `export_results` - `genotype_pca_loadings.csv`.

## Results

| Quantity | Value |
| --- | --- |
| Samples / variants | 50 / 28,522 |
| Polymorphic variants used | 4,388 |
| Eigenvalues (PC1-PC5) | 0.468376044939, 0.401771650144, 0.357612132983, 0.330650600133, 0.316326176133 |
| GRM diagonal mean | 0.15144147113 |
| Loading rows | 28,522 (zero for monomorphic sites) |

## External oracles

| Oracle | Comparison | Result |
| --- | --- | --- |
| plink2 2.00a6 `--pca 5` | eigenvalues | max abs 3.999e-07 (oracle prints 6 decimals) |
| plink2 `--pca 5` | PC scores | abs correlation 0.999999999999-1.0 |
| plink2 `--make-rel square` | GRM entries | max abs 4.728e-07 |
| plink2 `--pca 3 allele-wts` | ALT-allele loadings | max abs 5.044e-06 after per-component sign alignment |

The GRM divides by the total number of biallelic SNPs (28,522), including
monomorphic sites, which is the plink2 convention; dividing only by the 4,388
polymorphic sites would inflate every entry by 6.5x. PCA component signs are
arbitrary: the oracle aligns each component's sign before comparing loadings.
