# ATAC-seq QC route (GM12878)

Bulk ATAC-seq quality control on a real ENCODE experiment: fragment-size
distribution, TSS enrichment and peak/FRiP summary.

## Data provenance

| Input | Source | Size (bytes) | SHA256 |
| --- | --- | --- | --- |
| `ENCFF415FEC.bam` | ENCODE ENCSR095QNB (GM12878 ATAC-seq, GRCh38, ENCODE4 v1.9.1 alignment) | 2,515,550,487 | `08078e26e6cce95bf959d38941ff37693134601566193ef06851a9a3da910485` |
| `peaks.bed` | ENCODE ENCSR095QNB IDR thresholded peaks `ENCFF945SYZ` (narrowPeak, 155,153 records) | 9,819,405 | `d3312c42b0cc241d25b56fd032b026039388d7e3cfe4a1c8457b84a7b49d6fb9` |
| `tss.bed` | UCSC hg38 `refGene.txt.gz` (gene-level TSS: `txStart` on +, `txEnd-1` on -) | 998,500 | `a8ef7e106bd0c6ac2173302050fc8248def177dafdc17b42ab3f3a93b4d40b14` |

The BAM is coordinate-sorted with a `.bai` index; md5 `aca6bde5b395777573e7cf94a04c2024`
matches the ENCODE manifest. `tss.bed` keeps the 28,278 genes on chr1-22, X, Y.

## Steps

| # | Operator | Input | Export |
| --- | --- | --- | --- |
| 1 | `atac_fragment_size` | BAM | CSV (length histogram) |
| 2 | `export_results` | size table | CSV |
| 3 | `atac_tss_enrichment` | BAM + TSS BED | CSV (TSS x position) |
| 4 | `export_results` | TSS matrix | CSV |
| 5 | `atac_peak_quality` | BAM + peaks BED | CSV (statistic table) |
| 6 | `export_results` | peak table | CSV |

Fragment filters: primary alignments, paired, both mates mapped, no duplicates,
MAPQ >= 30, positive template length. `max_length` = 1000 keeps the
nucleosome-scale part of the distribution.

## Results (WSL, run 2026-11-07)

| Metric | Value |
| --- | --- |
| fragments (all / <= 1000 bp) | 22,857,207 / 22,737,035 |
| mean / median fragment length | 266.7552 / 209 bp |
| NFR (<100) / mononucleosome (180-247) / dinucleosome (300-400) | 0.269817 / 0.155362 / 0.111612 |
| nucleosome fraction (>=147) | 0.635754 |
| TSS sites | 28,278 |
| TSS center / flank mean | 3.938663 / 1.101277 |
| TSS enrichment score | 3.576452 |
| peaks | 155,153 (138,896,175 bp; mean 895.22; median 847) |
| fragments in peaks | 14,522,524 |
| FRiP | 0.635359 |
| fragments per peak | 93.6013 |

## Independent oracles

| Check | Oracle | Result |
| --- | --- | --- |
| fragment length histogram | `samtools view -f 0x1 -F 0xD04 -q 30` + awk over TLEN | per-length max abs diff **0**; total and length sum identical |
| TSS profile (100 x 10 bp bins, +/-500) | `bedtools intersect -sorted -c` over per-TSS windows | max abs **0.0**, Pearson **1.0**, center/flank/score identical |
| peak widths | `bedtools` over the same BED | 155,153 peaks, total bp / mean / median identical |
| FRiP | `bedtools intersect -u` fragments vs peaks | **14,522,524 / 22,857,207 = 0.6353586** identical |

## Limits

- `atac_fragment_size` reports lengths up to `max_length`; longer fragments are
  excluded from the table and from `n_fragments`, while `atac_peak_quality`
  uses all passing fragments (22,857,207).
- TSS bins are half-open windows in [-flank, flank); a fragment exactly at
  `-flank` belongs to the first bin and one at `+flank` is outside the profile.
- Only primary, properly paired fragments without duplicates are counted; this
  route does not model multi-mapping or mitochondrial reads.
- Paired-end BAM must be coordinate sorted and indexed; no re-alignment is done.
