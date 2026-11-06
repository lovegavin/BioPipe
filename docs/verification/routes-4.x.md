# Route verification for BioPipe 4.x

This page records incremental, three-platform verification of operator library
routes added after the 4.0.3 release. Every row is produced from a real,
publicly available dataset; synthetic inputs are never counted as biological
evidence.

Registry baseline after the first batch: **721 operators / 102 readers / 7
packages / 25 routes**, `errors 0`, `warnings 108`.

## Batch 1 - variant_qc_concordance

### Data provenance

| Source | Dataset | Subset | Size | SHA256 |
| --- | --- | --- | --- | --- |
| `query` | 1000 Genomes phase 3, chr22 (b37 slice distributed with the verification workdir) | `22:17,000,000-18,000,000`, 50 samples (49 random + NA12878) | 620,892 B, 30,104 records | `1b7c66cf2ba8e0aa0e683d4f89e98b9a9fa9fb7db74e428b1c58c975f4589a93` |
| `truth` | GIAB NA12878 NISTv3.3.2 GRCh37 high-confidence calls, `HG001_GRCh37_GIAB_highconf_...PGandRTGphasetransfer.vcf.gz` | `22:17,000,000-18,000,000`, sample `HG001` | 30,805 B, 846 records | `3479819a02009dca99eac878a6280bd674c27c829c4c44f8830e49e484a457f8` |

GIAB is distributed from
`https://giab.s3.amazonaws.com/release/NA12878_HG001/NISTv3.3.2/GRCh37/`.
The 1000 Genomes slice and the GIAB region both use b37 contig names without a
`chr` prefix.

Rebuild the inputs with `bcftools`:

```bash
bcftools view -r 22:17000000-18000000 -s NA12878,HG00096,... \
  chr22.first200k.vcf.gz -Oz -o query.vcf.gz
tabix -h -f https://giab.s3.amazonaws.com/release/NA12878_HG001/NISTv3.3.2/GRCh37/HG001_GRCh37_GIAB_highconf_CG-IllFB-IllGATKHC-Ion-10X-SOLID_CHROM1-X_v.3.3.2_highconf_PGandRTGphasetransfer.vcf.gz \
  22:17000000-18000000 | bgzip > truth.vcf.gz
tabix -p vcf truth.vcf.gz
```

### Route

`library/seed/routes/variant_qc_concordance/` contains the eight-step route:
`vcf_stats -> export_results -> vcf_filter -> export_results(native) ->
vcf_concordance -> export_results -> vcf_relatedness -> export_results`.

Run it with the standard task runner:

```bash
python scripts/run.py workdir/b1_route --check
python scripts/run.py workdir/b1_route --memory-mb 4096 --disk-mb 4096
```

### Results (identical on all three platforms)

| Step | Metric | Value |
| --- | --- | --- |
| `vcf_stats` | variants / SNPs / indels / other | 30,104 / 28,730 / 1,524 / 33 |
| | multiallelic / PASS | 172 / 30,104 |
| | transitions / transversions / Ts:Tv | 19,912 / 8,809 / 2.260415 |
| | mean QUAL / samples / chromosomes | 100.0 / 50 / 1 |
| `vcf_filter` | input / output / removed | 30,104 / 30,104 / 0 |
| | filtered VCF bytes | 10,349,708 |
| `vcf_concordance` | query ALT sites / truth ALT sites | 30,287 / 850 |
| | matched / truth-only / query-only | 797 / 53 / 29,449 |
| | duplicate query alleles skipped | 5 |
| | allele mismatches / genotype comparisons | 41 / 797 |
| | genotype discordant / concordance | 9 / 0.9887076537 |
| `vcf_relatedness` | samples / SNPs | 50 / 2,816 |
| | mean off-diagonal kinship | -0.026224 |
| | max off-diagonal kinship | 0.293938 |

Exported artifacts: `variant_stats.csv`, `concordance.csv`, `kinship.csv`
(50 x 50) and `filtered_variants.vcf`.

### Independent oracles

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| `bcftools norm -m -any` + `bcftools stats` | 1.25 (srv), 1.19 (WSL) | allele-level SNP / indel / other counts | exact (28,730 / 1,524 / 33), Ts:Tv 19,919/8,811 = 2.26 |
| `bcftools view -H -i 'QUAL>=20 && FILTER="PASS"'` | 1.19 | retained records | exact (30,104) |
| `bcftools isec` on split query/truth VCFs | 1.25 | shared / truth-only / query-only | exact (797 / 53 / 29,490) |
| `plink2 --make-king-table counts` on the same biallelic SNP set (`bcftools view -m2 -M2 -v snps`, 2,816 sites) | 2.0.0-a.7.13 | 1,225 pair kinship coefficients | max abs delta 5e-7, mean abs delta 1.1e-7, Pearson 1.0 |
| plink2 full SNP set (2,837 sites, multiallelic REF dosage included) | 2.0.0-a.7.13 | 1,225 pairs | mean abs delta 0.0013, max 0.0056, Pearson 0.999935 (scope difference, not an error) |

Tolerances used for the gate: integer counts exact; kinship `abs(delta) <=
1e-5`. The same-variant-set comparison passes with a 20x margin.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, bcftools 1.19, samtools 1.19.2.
- srv: Python 3.11.18 virtual environment, bcftools 1.25,
  `plink2 2.0.0-a.7.13`. The same commit was synced as a source archive; all
  eight step reports match WSL byte-for-byte apart from timing fields.
- Windows: Python 3.12.10, a Windows checkout; task runner and the Studio control
  API (`POST /api/v1/jobs`) both reproduce the same values. The API job was
  submitted by an agent token with `context`, `edit` and `run` scopes.
- All three runs use the same commit; compare scripts ignore paths, timings and
  `result_files` entries and report `DIFFS 0`.

### Platform gap fixed in this batch

`.vcf.gz` inputs were previously claimed by `VcfReader`, which decodes a
genotype matrix, so no operator could receive a raw VCF file. Batch 1 adds
`VcfFileReader` (`library/seed/src/reader/readers/vcf_file_reader.py`), a
metadata-only reader that returns a `FileArtifact` with representation `vcf`.
Routes select it explicitly with `reader: VcfFileReader`. Reader count moves
from 101 to 102; operator code and protocol v3 semantics are unchanged.

### Known limits

- `vcf_relatedness` intentionally restricts to biallelic SNPs, MAF >= 0.05,
  call rate >= 0.9, and the first 50 samples by default. plink2 includes
  multiallelic REF dosages, which explains the 21 extra sites in the full-set
  comparison; the same-set comparison removes that scope difference.
- `vcf_concordance` compares ALT alleles, not records. A query record with two
  ALT alleles contributes two sites; truth-only ALT alleles are counted
  separately.
- Duplicate query records with the same ALT are skipped and reported as
  `n_query_duplicates` instead of aborting the run.
