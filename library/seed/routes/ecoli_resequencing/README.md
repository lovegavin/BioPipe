# ecoli_resequencing

Alignment QC, pileup variants and majority consensus on real E. coli K-12
resequencing reads, with an independent samtools/bcftools oracle for every
operator.

## Data

| Role | File | Bytes | SHA256 |
|---|---|---|---|
| Alignments | `input/alignment.bam` | 19,134,169 | `79e4140a615f96f839b065a9684bfe37939c056349da01772584f0e1d54b481e` |
| Reference | `input/ecoli.fasta` | 4,699,745 | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

The BAM is the output of the `sequencing_qc` route: 200,000 read pairs from
ENA run `SRR001666` (E. coli K-12, 2x250 bp) aligned with bwa 0.7.17-r1188
(`bwa mem -5SP`) to `GCF_000005845.2_ASM584v2_genomic.fna` (E. coli K-12
MG1655, 4,641,652 bp). It is deliberately left unsorted to exercise the
single-pass readers; the samtools oracle sorts a copy first.

Rebuild from the source data:

```bash
gzip -dc SRR001666_1.fastq.gz | head -n 800000 | gzip -1 > reads_1.fastq.gz
gzip -dc SRR001666_2.fastq.gz | head -n 800000 | gzip -1 > reads_2.fastq.gz
bwa index ecoli.fasta
bwa mem -5SP -t 4 ecoli.fasta reads_1.fastq.gz reads_2.fastq.gz \
  | samtools view -b -o alignment.bam
```

## Steps

`sources` -> `alignment_coverage` -> `alignment_insert_size` ->
`pileup_variants` -> `consensus_sequence`, each followed by `export_results`
(8 steps in total).

## Results (WSL, 12.3 s total)

| Operator | Key values |
|---|---|
| `alignment_coverage` | 4,641,652 bp; mean depth 2.888806; covered 4,356,245; breadth 1x 0.938512, 5x 0.172446, 10x 0.001283; max depth 16 |
| `alignment_insert_size` | 177,197 pairs; mean 37,955.427; median 489; std 299,454.819; p25/p75 475/503 |
| `pileup_variants` | 0 variants over 481,205 covered positions (depth >= 5) |
| `consensus_sequence` | 4,641,652 bases; 481,205 called; 4,160,447 N; 0 substitutions |

## Oracle (independent implementations)

| Operator | Oracle | Command | Comparison |
|---|---|---|---|
| `alignment_coverage` | samtools 1.19.2 | `samtools sort`; `samtools coverage`; `samtools depth -a` | numreads 372,959 = n_mapped; meandepth 2.88881 vs 2.888806 (rounding); covbases 4,356,245 = covered_bases; b5 800,435, b10 5,955, max 16 agree exactly |
| `alignment_insert_size` | samtools 1.19.2 | `samtools view -f 0x41 -F 0x904` then TLEN column | n 177,197; mean 37,955.427033; median 489; std 299,454.819; p25/p75 475/503 -- all exact |
| `pileup_variants` | bcftools 1.19 | `bcftools mpileup -f ecoli.fasta -q 0 -Q 20 -d 10000` \| `bcftools call -mv` | 0 calls = 0 variants |
| `consensus_sequence` | samtools 1.19.2 | `samtools consensus -m simple -d 5 -c 0.6 --min-BQ 20 --show-del yes -a` | 4,641,652 bases; 481,205 called; identical at all 481,205 positions; 0 substitutions in both |

Tolerances: counts and exact extrema are exact; depth, insert-size and
consensus comparisons are exact at floating point equality (~1e-12 relative).
`samtools consensus` requires `--show-del yes` to keep reference coordinates;
without it the output drops deleted bases and shifts.

## Limitations

- `pileup_variants` and `consensus_sequence` work in reference coordinates:
  insertions are not represented and deletions leave the reference base.
  This is intentional for a majority consensus, not a full indel-aware call.
- `alignment_insert_size` uses absolute TLEN of primary, paired reads with
  both mates mapped; it does not require the proper-pair flag because this
  fixture has none (bwa `-5SP` on unsorted reads). The median is the robust
  summary; the mean is inflated by chimeric pairs (max 4.6 Mb).
- All four operators are pure Python, so the same route runs on Windows
  without samtools/bcftools.
