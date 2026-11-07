# GWAS association on chr22

Linear association testing for common variants on a small 1000 Genomes chr22
panel, using a synthetic phenotype built on real genotypes.

## Inputs

| file | size | sha256 |
| --- | --- | --- |
| input/subset_snps.vcf.gz | 541728 | 57c1870b83244ae3ba74880f89a1ef69b508bfecad50e8bc998e233a2d060c05 |
| input/pheno.csv | 1089 | 0ef76db1eb248b129688f3bf6dd7e5516e9567ce26aa04d163b464ae8243fc50 |

`subset_snps.vcf.gz` is the 1000G chr22 17.0-18.0 Mb biallelic SNP subset
(28,522 variants, 50 GBR samples; 4,388 polymorphic in this panel).
`pheno.csv` is a **synthetic** phenotype: 20 causal variants drawn with seed 7,
standard normal noise, standardised and median-split into 0/1
(`mode = synthetic phenotype on real genotypes`).

## Steps

1. `gwas_association` - linear regression per variant (`min_maf` 0.05, 2,816 tested).
2. `export_results` - association table.
3. `gwas_inflation` - genomic control lambda from chi-square quantiles.
4. `export_results` - inflation summary.
5. `gwas_top_hits` - distance clumping (`threshold` 0.001, 1 Mb window).
6. `export_results` - lead variants.

## Results

- 2,816 variants tested, minimum p = 3.61e-4.
- Genomic inflation lambda = 1.1048 (mean chi2 1.1796, median p 0.4783).
- One lead variant: 22:17839358:C:T, beta -0.8725, p = 3.61e-4.

## Oracles

| oracle | check | result |
| --- | --- | --- |
| plink2 2.00a6 `--glm` | 2,816 shared variants, beta/SE/P after A1 alignment | beta 4.65e-6 (6-digit print), SE 5.0e-7, P 5.0e-7 |
| plink2 2.00a6 | lambda over the same 2,816 variants | 1.10484799 vs 1.10484682, diff 1.17e-6 |
| base R 4.3.3 `lm` | beta/SE/P on the same variants | max abs 3.55e-15 / 9.4e-16 / 1.1e-15 |

## Notes and limitations

- The phenotype is synthetic; results are an algorithm check, not a biological
  finding. Pair it with a real phenotype to interpret associations.
- All 50 samples are from one population (GBR), so no covariates or
  population-structure correction are needed here; the operator supports an
  optional covariate table.
- The top-hit threshold 0.001 is relaxed for this small panel; the operator
  default is the genome-wide 5e-8.
