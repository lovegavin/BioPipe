# BAM alignment quality control (bam_alignment_qc)

Alignment-level QC on a BAM file: mapping-quality distribution, observed
read-length distribution and a compact alignment summary.

## Data

| Input | Size | SHA-256 |
|---|---|---|
| `region.bam` (ENCODE GM12878 ATAC-seq, chr22 region) | 1,849,147 B | `ce040a8bdd467c4da4b38895e8781a4b38d1fdcd444ba75b0d78c96a163a370d` |

The region holds 35,456 primary, properly paired, mapped reads with 80
distinct query lengths (6–101 bp). MAPQ values include 255 ("unavailable"),
which the operators cap at 60 for the histogram and the mean.

## Steps

1. `bam_mapq_distribution` → `mapq_distribution` (CSV)
2. `bam_read_length_stats` → `read_length_stats` (CSV)
3. `bam_alignment_summary` → `alignment_summary` (CSV)

## Results (WSL)

| Metric | Value |
|---|---|
| total / mapped reads | 35,456 / 35,456 (1.0) |
| proper-pair fraction | 1.0 |
| reverse fraction | 0.499887 |
| duplicates / clipped bases per read | 0 / 0.0 |
| mean MAPQ (capped at 60) | 56.8434 |
| MAPQ ≥ 20 / ≥ 30 | 0.963278 / 0.960232 |
| MAPQ 60 reads | 32,622 (0.920070) |
| read length mean / min / max | 90.5904 / 6 / 101 |
| distinct read lengths | 80 |

Export MD5: summary `258198c22b4b8d0fbba6ec337ae53111`, MAPQ
`782779f95584bacf472fbe416a8c4a3a`, read length
`d78b86a620ee0795640d6fe28d8d91b8`.

## Oracles

* **pysam 0.24.1** (independent BAM parser): MAPQ histogram, read-length
  histogram and 13 summary counts match exactly (`max_abs 0.0`).
* **samtools 1.19.2** `stats`: raw total and mapped read counts match.
* Independent recomputation of `mean_mapq`, reverse fraction and clipped
  counts from the same records also matches exactly.

Result file: `workdir/b44_oracle.json` (`passed: true`).

## Limitations

* Single genomic region (chr22), not a whole-genome BAM.
* MAPQ 255 is reported as 60 in the histogram and in `mean_mapq`; the raw
  value is not exposed separately.
* Read lengths above `max_length` (default 1000) are folded into one overflow
  row; none occur here.
* Duplicate marking is taken from the BAM flag; no duplicate re-marking is
  performed.
