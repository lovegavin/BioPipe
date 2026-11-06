# E. coli gene-level counts

Per-gene alignment counting, TPM/FPKM/CPM normalisation and 5'/3' coverage
bias from a real *E. coli* K-12 resequencing alignment.

## Data

| Input | Size | SHA256 | Source |
| --- | --- | --- | --- |
| `input/ecoli.sorted.bam` | 19,134,169 B | `79e4140a…` | B3 route, `bwa mem` of SRR001666 200k pairs, coordinate sorted + indexed |
| `input/ecoli.gff` | 2,314,238 B | `68d25735ccde6d37af68613dca57a588ae69423f0ecee99b0f29d596eff7accb` | NCBI `GCF_000005845.2_ASM584v2_genomic.gff.gz`, 9,531 lines |

4,506 genes with `locus_tag`; genome length 4,641,628 bp.

## Route

| # | Operator | Input | Output |
| --- | --- | --- | --- |
| 1 | `bam_gene_counts` | BAM + GFF | counts / length / cpm |
| 2 | `export_results` | counts | CSV |
| 3 | `counts_normalize` | counts | tpm / fpkm / cpm |
| 4 | `export_results` | normalised | CSV |
| 5 | `bam_gene_bias` | BAM + GFF | five_prime_density / three_prime_density / ratio |
| 6 | `export_results` | bias | CSV |

Parameters: `min_mapq 30`, `feature_type gene`, `id_attribute locus_tag`,
`bins 5`, `count_pairs false`.

## Results (WSL, 2.03 s total)

- 4,506 genes, **328,624** counted alignments.
- `b0001`: 10 counts, length 66, CPM 30.429914; TPM 397.275958, FPKM 461.059300.
- `b0001` bias: 5' 0.227273, 3' 0.303030, ratio 0.75.

## Oracle

| Comparison | Method | Max abs diff |
| --- | --- | --- |
| counts | `bedtools multicov` on a `samtools view -q 30 -F 0xB04` filtered BAM | **0** (4,506/4,506 genes, 0 mismatches) |
| TPM / FPKM / CPM | recomputed from counts and length with the standard formulas | **0.0** |
| 5'/3' density ratio | `samtools view` re-parsed independently (CIGAR span, midpoint, 5 equal bins) | **0.0** |

## Limits

- Only primary alignments (secondary/supplementary/qcfail excluded) and
  `mapq >= min_mapq` are counted; duplicate-flagged reads are kept, matching
  `bedtools multicov` defaults.
- A read counts once for every gene its reference span overlaps; reads that
  overlap no gene are ignored.
- GFF/GTF coordinates are converted to 0-based half-open before overlap tests.
- Paired-end counting (`count_pairs`) uses read 1 only, so a fragment is
  counted once.
