# Route verification for BioPipe 4.x

This page records incremental, three-platform verification of operator library
routes added after the 4.0.3 release. Every row is produced from a real,
publicly available dataset; synthetic inputs are never counted as biological
evidence.

Registry baseline after the first batch: **721 operators / 102 readers / 7
packages / 25 routes**, `errors 0`, `warnings 108`. After the second batch:
**725 operators / 103 readers / 7 packages / 26 routes**, `errors 0`, `warnings
108`.

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

## Batch 2 - sequencing_qc

### Data provenance

| Source | Dataset | Subset | Size | SHA256 |
| --- | --- | --- | --- | --- |
| `reads_1` | ENA `SRR001666`, Escherichia coli K-12 MG1655 paired-end reads | first 200,000 pairs | 8,291,336 B | `5b512b0bd02c906186c48aa76d20b3ba4d6f3423a317671523c0d01005571586` |
| `reads_2` | same run, mate 2 | first 200,000 pairs | 9,356,844 B | `1e35a3053055b4d229fa37b9367028251860c47b06a9a947309fc287722d8088` |
| `ecoli.fasta` | NCBI `GCF_000005845.2` (ASM584v2), E. coli K-12 MG1655 | complete genome | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

The 200,000-pair subset is a prefix of the real run, not synthetic data. Rebuild
it with:

```bash
curl -O https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR001/SRR001666/SRR001666_1.fastq.gz
curl -O https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR001/SRR001666/SRR001666_2.fastq.gz
gzip -dc SRR001666_1.fastq.gz | head -n 800000 | gzip -1 > reads_1.fastq.gz
gzip -dc SRR001666_2.fastq.gz | head -n 800000 | gzip -1 > reads_2.fastq.gz
```

### Route

`library/seed/routes/sequencing_qc/` contains the nine-step route:
`fastq_stats -> export_results -> fastq_quality_profile -> export_results ->
fastq_adapter_scan -> export_results -> align_reads -> bam_flagstat ->
export_results`. `align_reads` runs `bwa index`, `bwa mem -5SP` and
`samtools view -b`; the `reads` source declares `mate_path: reads_2.fastq.gz`.

```bash
python scripts/run.py workdir/b2_route --check
python scripts/run.py workdir/b2_route --memory-mb 4096 --disk-mb 4096
```

### Results (identical on all three platforms)

| Step | Metric | Value |
| --- | --- | --- |
| `fastq_stats` | reads / bases | 200,000 / 7,200,000 |
| | length min / max / mean | 36 / 36 / 36 |
| | GC fraction | 0.5080722222 |
| | mean quality / Q20 / Q30 | 34.71771889 / 0.8753909722 / 0.7919225 |
| | reads containing N | 1,231 |
| `fastq_quality_profile` | cycles | 36 |
| | first-cycle mean quality | 39.893625 |
| `fastq_adapter_scan` | illumina / nextera / small-RNA reads | 2 / 2 / 2 |
| `align_reads` | BAM records | 400,000 |
| | wall time (WSL / srv) | 6.829 s / 16.119 s |
| `bam_flagstat` | total / primary / mapped | 400,000 / 400,000 / 372,959 |
| | read1 / read2 | 200,000 / 200,000 |
| | properly paired / both mapped | 0 / 354,394 |
| | singletons / duplicates / secondary / supplementary | 18,565 / 0 / 0 / 0 |

The four exported CSVs are byte-identical on all three platforms:

| Artifact | MD5 |
| --- | --- |
| `fastq_stats.csv` | `65e64ac9328a9cedb2985f94af00b5f1` |
| `quality_profile.csv` | `0aa3198dc73232eaa30b47f59ba06352` |
| `adapter_scan.csv` | `13547050dc7f753e2209f7097e67ea72` |
| `bam_flagstat.csv` | `59e1ce934f4e25256f546410ee8d7327` |

### Independent oracles

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| Biopython `SeqIO` re-implementation | 1.86 | 10 summary statistics + 36 per-cycle mean qualities | abs delta 0.0 for every value |
| `seqkit stats -a` | 2.9.0 | reads, bases, length, Q20, Q30, GC, N bases | matches to the printed precision (87.54%, 79.19%, 50.81%, 6,153 N bases) |
| `cutadapt -a <adapter> -O 8 -e 0` | 5.2 | reads carrying each 3-prime adapter | exact: 2 / 2 / 2 |
| `samtools flagstat` | 1.19.2 | all 16 flagstat counters | exact for every counter |

The adapter comparison is the reason the operator anchors matches at the 3-prime
end: an anywhere-in-read 8-mer search reported 52 / 32 / 58 reads, which is
random background, while cutadapt and the 3-prime implementation both report 2.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, bwa 0.7.17-r1188, samtools 1.19.2.
- srv: Python 3.11.18 virtual environment, bwa 0.7.19-r1273, samtools 1.22.1.
  The same commit was synced as a source archive; step reports differ only in
  artifact paths and `mtime_ns`.
- Windows: Python 3.12.10. bwa and samtools are not installed, so the alignment
  step is recorded as `SKIP(no bwa/samtools)` and the platform runs two
  sub-routes: `b2_fastq` (six FASTQ steps) and `b2_bam` (`BamFileReader` over the
  BAM produced on srv, then `bam_flagstat`). Both finish and reproduce the same
  CSV bytes.
- The Studio control API (`POST /api/v1/jobs`) is covered in batch 1; batch 2
  uses the task runner on all three platforms.

### Known limits

- `fastq_adapter_scan` reports reads whose 3-prime end matches an adapter
  prefix; internal adapter fragments are deliberately not counted.
- `bam_flagstat` parses BAM (BGZF) directly. SAM and CRAM inputs are out of
  scope for this operator.
- Windows cannot execute `align_reads` without bwa/samtools; this is an
  environment gate, not an operator failure.
