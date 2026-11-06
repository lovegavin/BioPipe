# Read preprocessing

FASTQ quality trimming, adapter trimming and exact-sequence deduplication on a
public ENA read set.

## Inputs

| File | Size | SHA-256 |
| --- | --- | --- |
| `input/reads_1.fastq.gz` | 8,291,336 B | `5b512b0b…` |
| `input/reads_2.fastq.gz` | 9,356,844 B | `1e35a305…` |

`reads_1.fastq.gz`/`reads_2.fastq.gz` are the first 200,000 read pairs of ENA
run [SRR001666](https://www.ebi.ac.uk/ena/browser/view/SRR001666) (Illumina
36 bp single-end reads, *E. coli*). The route uses mate 1 only; mate 2 is kept
so the pair can be reused by alignment routes. The upstream reference is
*E. coli* K-12 MG1655 GCF_000005845.2.

## Route

```
reads ──> fastq_quality_trim ──> export_results
      ├─> fastq_adapter_trim ──> export_results
      └─> fastq_deduplicate  ──> export_results
```

Each operator reports a Form summary (`statistic`, `value`) and writes the
processed reads as a native FASTQ artifact (`<name>.fastq`). The FASTQ is
registered through `result_files`; the Form summary is exported to CSV.

Parameters: quality trim `min_quality=20`, `min_length=20`; adapter trim
Illumina universal adapter `AGATCGGAAGAGCACACGTCTGAACTCCAGTCAC`, `min_overlap=3`,
`max_mismatches=0`; deduplication on exact sequences.

## Results (200,000 reads)

| Operator | Result |
| --- | --- |
| `fastq_quality_trim` | 194,355 reads kept (5,645 dropped), 6,687,525 bases, 512,475 bases trimmed, 83,085 reads trimmed |
| `fastq_adapter_trim` | 3,244 reads with adapter, 7,189,076 bases, 10,924 bases trimmed |
| `fastq_deduplicate` | 197,031 unique sequences, 2,969 duplicates, fraction 0.014845 |

## Oracles

| Operator | Oracle | Version | Comparison |
| --- | --- | --- | --- |
| `fastq_quality_trim` | cutadapt `-q 20 -m 20` | 5.2 | 194,355 reads / 6,687,525 bases; output FASTQ md5 `d4c039de4822593401950fc92abb1f2c` identical |
| `fastq_adapter_trim` | cutadapt `-a … -O 3 -e 0 --no-indels` | 5.2 | 3,244 reads with adapter / 7,189,076 bases; output FASTQ md5 `5b492c0d44347932bc7e79858c102a6f` identical |
| `fastq_deduplicate` | `seqkit fx2tab \| cut -f2 \| sort -u` | 2.9.0 | 197,031 unique sequences identical |

cutadapt's `quality_trimmed` count (433,109) excludes bases lost with reads
removed for being shorter than 20 bp; adding those 79,366 bases gives the
operator's 512,475 trimmed bases.

`seqkit rmdup -s` reports 195,398 because its default treats a read and its
reverse complement as duplicates. The operator exposes
`collapse_reverse_complements` (default `false`) for that convention; the
route compares against the exact-sequence count.

## Limitations

- Deduplication is exact-sequence only by default; UMI-aware or
  quality-aware collapse is out of scope.
- Adapter matching is ungapped and 3'-anchored; `max_mismatches` applies to
  the partial overlap case.
- FASTQ export is a native artifact: `export_results` does not carry FASTQ
  text into CSV.
