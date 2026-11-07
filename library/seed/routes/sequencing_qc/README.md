# sequencing_qc

Read-level QC and alignment summary on a real paired-end E. coli dataset.

## Data

| Role | Source | Size |
| --- | --- | --- |
| reads 1 | ENA `SRR001666_1.fastq.gz` (E. coli K-12 MG1655) | 260,786,393 B full file |
| reads 2 | ENA `SRR001666_2.fastq.gz` | 292,718,968 B full file |
| reference | NCBI `GCF_000005845.2_ASM584v2_genomic.fna.gz` | 4.7 MB |

The route input is the first 200,000 read pairs of the ENA run, so the route
stays runnable on a laptop while every read is real sequencing data:

```bash
gzip -dc SRR001666_1.fastq.gz | head -n 800000 | gzip > reads_1.fastq.gz
gzip -dc SRR001666_2.fastq.gz | head -n 800000 | gzip > reads_2.fastq.gz
gzip -dc GCF_000005845.2_ASM584v2_genomic.fna.gz > ecoli.fasta
```

## Steps

`fastq_stats` and `fastq_quality_profile` stream the FASTQ records; `fastq_adapter_scan`
counts reads containing the standard Illumina, Nextera or small-RNA adapter prefix;
`align_reads` (existing operator) runs `bwa mem -5SP` and `samtools view -b`;
`bam_flagstat` decodes the resulting BAM and reproduces the `samtools flagstat`
counter set.

## Oracles

Measured on the 200,000-pair subset:

| Metric | Oracle | Command | Result |
| --- | --- | --- | --- |
| reads, bases, lengths, GC, Q20/Q30, mean quality, reads with N | Biopython 1.8x | independent parse of `reads_1.fastq.gz` | 10/10 values and 36 per-cycle means differ by 0.0 |
| same summary (rounded) | seqkit 2.9.0 | `seqkit stats -a reads_1.fastq.gz` | Q20 87.54%, Q30 79.19%, GC 50.81%, sum_n 6153 - agrees within the printed precision |
| adapter-positive reads | cutadapt 5.2 | `cutadapt -a <adapter> -O 8 -e 0 -j 4 reads_1.fastq.gz` | 2 for each of the three adapters, matching the 3-prime anchored count |
| flagstat counters | samtools 1.19.2 | `samtools flagstat aligned.bam` | all 16 counters equal (400000 total, 372959 mapped, 18565 singletons, 0 properly paired) |

Counts are expected to be exact; rates are compared at 1e-6 and per-cycle
quality at 1e-2 absolute tolerance. fastp was not available as a binary for
this environment, so the sequence-level oracle is Biopython plus seqkit rather
than fastp.

## Running

```bash
python -m operon --workspace "$PWD" run library/seed/routes/sequencing_qc/route.operon.zip
```

or from a source checkout:

```bash
python scripts/run.py workdir/b2_route --check
python scripts/run.py workdir/b2_route --memory-mb 4096 --disk-mb 4096
```

The alignment step requires `bwa` and `samtools` on `PATH`; without them the
route stops after the three FASTQ steps. That is a resource skip, not a data
skip.
