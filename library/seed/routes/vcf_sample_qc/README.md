# VCF sample and site quality control

This route exercises three operators that summarise per-sample genotype quality
and per-site Hardy-Weinberg behaviour from a VCF file:

- `vcf_sample_stats` — per-sample call rate, genotype counts, heterozygosity
  ratio and transition/transversion ratio.
- `vcf_site_missingness` — per-site called/missing counts and call rate.
- `vcf_hardy_weinberg` — per-site exact Hardy-Weinberg test (Wigginton et al.
  2005) with observed and expected heterozygosity.

## Data

| File | Source | Size | SHA256 |
| --- | --- | --- | --- |
| `input/subset_snps.vcf.gz` | 1000 Genomes phase 3, chr22:17,000,515-18,000,000, 50 GBR samples, biallelic SNPs | 541,728 B | `57c1870b83244ae3ba74880f89a1ef69b508bfecad50e8bc998e233a2d060c05` |

The subset contains 28,522 biallelic SNP sites and no missing genotypes. It is a
real population panel; no synthetic genotypes are used.

## Route

| Step | Operator | Input | Output |
| --- | --- | --- | --- |
| 1 | `vcf_sample_stats` | genotypes | sample_stats |
| 2 | `export_results` | sample_stats | `vcf_sample_stats.csv` |
| 3 | `vcf_site_missingness` | genotypes | site_missingness |
| 4 | `export_results` | site_missingness | `vcf_site_missingness.csv` |
| 5 | `vcf_hardy_weinberg` | genotypes | hardy_weinberg |
| 6 | `export_results` | hardy_weinberg | `vcf_hardy_weinberg.csv` |

## Results (WSL)

- 50 samples x 28,522 sites; every site has call rate 1.0.
- Example sample `HG00096`: 28,522 called, 791 heterozygous, 27,074 hom-ref,
  657 hom-alt, het/hom ratio 0.028524, Ti/Tv 2.284431.
- Across samples: mean heterozygote count 962.1, mean Ti/Tv 2.284431.
- Hardy-Weinberg: median p = 1.0, minimum p = 6.08e-09; 4 sites below 1e-6 and
  147 sites below 0.05, consistent with a random subset of common variants.

## Oracles

| Oracle | Version / command | Result |
| --- | --- | --- |
| plink2 | 2.00a6, `--missing --het --hardy --freq --set-all-var-ids @:#` | missing/called/het counts exact; site missingness 0; HWE observed het exact, expected het 5.3e-15, p max 4.89e-7 |
| base R | 4.3.3, independent VCF parser and Wigginton exact test | counts exact; Ti/Tv 8.9e-16; HWE p max 5.0e-16 |
| bcftools | 1.19, `bcftools stats` | TSTV ts 19,838 / tv 8,684 / ratio 2.28, matching the per-sample 2.284431 |

## Limitations

- The exact HWE test assumes unrelated individuals and biallelic SNPs; no
  mid-p adjustment is applied.
- Ti/Tv is defined for biallelic A/C/G/T SNPs; other records are skipped.
- The route data has no missing genotypes, so call-rate checks are trivially
  1.0 and missingness handling is covered only by unit tests.
- Multiallelic records are ignored by all three operators.
