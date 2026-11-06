# Variant QC and concordance

Exercises `vcf_stats`, `vcf_filter`, `vcf_concordance` and `vcf_relatedness`
on public variant calls and exports every result, including the filtered VCF
as a native file.

## Inputs

| File | Source | Build | Size |
| --- | --- | --- | --- |
| `input/query.vcf.gz` | 1000 Genomes phase 3 release, `chr22.first200k.vcf.gz` slice (2504 samples), 49 unrelated samples + NA12878 | GRCh37/b37 | 620,892 B, 30,104 records, 50 samples |
| `input/truth.vcf.gz` | GIAB NA12878 HG001 NISTv3.3.2 high-confidence calls, chr22:17,000,000-18,000,000 | GRCh37 | 30,805 B, 846 records, 1 sample (HG001) |

Both files are subsets of the public releases; they are not committed to the
repository. Recreate them with `bcftools` 1.19+:

```bash
# query: chr22:17,000,000-18,000,000, 49 unrelated 1000G samples plus NA12878
bcftools query -l chr22.first200k.vcf.gz | grep -vx NA12878 | head -49 > samples.txt
echo NA12878 >> samples.txt
bcftools view -r 22:17000000-18000000 -s "$(paste -sd, samples.txt)" \
  -Oz -o input/query.vcf.gz chr22.first200k.vcf.gz
tabix -f -p vcf input/query.vcf.gz

# truth: the same interval from the GIAB high-confidence release.  The GIAB
# file uses contigs named 1..22 (no "chr" prefix) and its chr22 high-confidence
# block starts at 17,278,430.
tabix -h https://giab.s3.amazonaws.com/release/NA12878_HG001/NISTv3.3.2/GRCh37/HG001_GRCh37_GIAB_highconf_CG-IllFB-IllGATKHC-Ion-10X-SOLID_CHROM1-X_v.3.3.2_highconf_PGandRTGphasetransfer.vcf.gz \
  22:17000000-18000000 | bgzip > input/truth.vcf.gz
tabix -f -p vcf input/truth.vcf.gz
```

## Expected results

WSL, run `20261106T155502-0e2c04d5fd31`, 8/8 steps in 0.93 s:

| Step | Value |
| --- | --- |
| `vcf_stats` | 30,104 variants, 28,730 SNPs, 1,524 indels, 33 other, ts/tv 2.260415, 50 samples |
| `vcf_filter` | 30,104 / 30,104 records retained, 10,349,708 B VCF |
| `vcf_concordance` | 797 matched alleles, 53 truth-only, 29,449 query-only, 41 allele mismatches, genotype concordance 0.988708 |
| `vcf_relatedness` | 50 samples x 2,816 biallelic SNPs, mean off-diagonal kinship -0.026224 |

## Oracle checks

| Metric | Independent implementation | Result |
| --- | --- | --- |
| SNP / indel / other counts, ts/tv | `bcftools stats` after `bcftools norm -m -any` | 28,730 / 1,524 / 33, ts/tv 2.26; exact match |
| retained records | `bcftools view -H -i 'QUAL>=20 && FILTER="PASS"' \| wc -l` | 30,104; exact match |
| shared / truth-only / query-only alleles | `bcftools isec` on `bcftools norm -m -any` splits | 797 / 53 / 29,490; exact match against matched / truth-only / query-only + allele-mismatch |
| kinship, identical SNP set | `plink2 --make-king-table counts` on `bcftools view -m2 -M2 -v snps` | 1,225 pairs, mean KINSHIP -0.02622374 vs -0.02622373, mean abs diff 1.1e-7, max 5e-7, Pearson 1.0 |
| kinship, full plink2 SNP set | same command on the unfiltered VCF | 1,225 pairs, max abs diff 0.0056, Pearson 0.99994 |

Tolerances: variant counts are exact; concordance counts are exact; kinship is
compared at `abs <= 1e-5` on the identical biallelic SNP set.

`vcf_relatedness` implements KING-robust Eq. 11 (between-family, the estimator
used by plink2 `--make-king-table`):

```
phi = 1/2 - (N_IBS1 + 4 N_IBS0) / (4 min(N_Aa(i), N_Aa(j)))
N_IBS1 = N_Aa(i) + N_Aa(j) - 2 N_Aa,Aa
```

The operator restricts to biallelic SNPs, while plink2 keeps multiallelic SNP
records using REF-allele dosage.  That accounts for 21 of 2,837 variants here
and for the larger deviation in the full-set comparison; on the identical
variant set the two implementations agree to single-precision rounding.

## Notes

`vcf_relatedness` caps the sample set (`max_samples`, default 50) because the
KING-robust matrix is quadratic in samples; passing all 2504 samples of the
source slice is intentionally out of scope.
