# Linkage disequilibrium analysis (1000 Genomes chr22)

Seven-step route on a 1000 Genomes phase 3 chr22 slice: drop low-MAF variants,
build an r-squared matrix, summarise LD decay by distance bin, and prune
correlated variants.

## Input

| File | Size | SHA-256 | Notes |
| --- | --- | --- | --- |
| `input/query.vcf.gz` | 620,892 B | `1b7c66cf2ba8e0aa0e683d4f89e98b9a9fa9fb7db74e428b1c58c975f4589a93` | 1000 Genomes phase 3 chr22 17-18 Mb, 50 samples, 30,104 records |

`bcftools norm -m -any` splits the multiallelic records into 30,287 biallelic
alternate alleles; the parse step counts 30,287 variants before filtering.

## Route

1. `genotype_filter` - min_maf 0.05, max_missing_rate 0.05.
2. `ld_matrix` - max_variants 500, complete-case r-squared matrix.
3. `export_results` - `ld_matrix.csv`.
4. `ld_decay` - max_distance 200,000 bp, 10 bins of 20 kb.
5. `export_results` - `ld_decay.csv`.
6. `ld_prune` - window 50 variants, r2 0.2.
7. `export_results` - `ld_prune.csv` (genotype matrix of the retained variants).

## Results (WSL, 4.74 s wall, 202,540 KB peak RSS)

| Step | Result |
| --- | --- |
| `genotype_filter` | 30,287 in, 3,306 kept, 26,981 dropped for MAF, 0 for missingness |
| `ld_matrix` | 500 x 500; 124,750 pairs; mean r2 0.0350392, max 1.0, q90 0.0740741 |
| `ld_decay` | 1,950,591 pairs in 10 bins; first bin 237,973 pairs, mean r2 0.205632 |
| `ld_prune` | 430 variants retained |

The filtered set has 3,305 distinct `CHROM:POS:ALT` labels: three records share
`22:17996285:ATCTC` after multiallelic splitting and are renamed by the VCF
reader. `ld_matrix` uses the first 500 retained labels in file order.

## Independent checks

| Check | Tool / version | Result |
| --- | --- | --- |
| Matrix pairs | plink2 v2.0.0-b.1.3 `--r2-unphased --ld-window-r2 0` | 124,750 pairs, max abs diff 5.0e-7, mean 2.8e-8 (plink prints 6 decimals) |
| Decay bins | plink2 on `--maf 0.05 --geno 0.05` subset | same 3,306 variants, 1,950,591 pairs; per bin n_pairs within 6, mean r2 within 4.6e-6, median within 1.5e-6 |
| Prune membership | NumPy greedy reimplementation | 431 vs 430 retained; difference is the duplicated `CHROM:POS:ALT` records, unique MAF membership identical (3,305 labels) |
| Prune property | NumPy r2 on retained pairs with input index gap <= 50 | 2,819 pairs, max r2 0.1994479 <= 0.2 |

## Limitations

- r-squared is unphased and computed from dosages, so it matches `--r2-unphased`
  but not haplotype-based `--r2-phased`.
- MAF uses alternate-allele dosages from the VCF; multiallelic records are split
  first, which is why the variant count differs from the raw record count.
- `ld_prune` windows count variants, not base pairs.
- plink2 writes r-squared with six decimals; comparisons inherit that rounding.
