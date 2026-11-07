# FASTQ composition QC: duplication, over-representation and GC

Real-data route for the FASTQ composition operators. Input is the first 200,000
read pairs of ENA run SRR001666 (Illumina 36 bp), the same subset used by the
read-preprocessing route.

## Data

| file | bytes | sha256 |
|---|---|---|
| `reads_1.fastq.gz` | 8,291,336 | `5b512b0bd02c906186c48aa76d20b3ba4d6f3423a317671523c0d01005571586` |

## Steps

1. `fastq_duplication_profile` — 15 duplication levels (1..9, >10, >50, >100,
   >500, >1k, >10k+) with sequence counts.
2. `export_results` — CSV.
3. `fastq_overrepresented` — sequences at or above 0.1% of the library.
4. `export_results` — CSV.
5. `fastq_gc_distribution` — per-read GC histogram (0..100%).
6. `export_results` — CSV.

## Results (WSL, 0.206 + 0.213 + 0.262 s)

| metric | value |
|---|---|
| reads | 200,000 |
| unique sequences | 197,031 |
| deduplicated | 98.5155% |
| level 1 / level 2 / level 3 | 194,132 / 2,835 / 60 |
| over-represented sequences (>=0.1%) | 0 |
| mean / median GC | 50.8126 / 50% |
| GC standard deviation / mode | 10.0358 / 53% |

Exports are byte-identical to `fastq_duplication_profile.csv` (406 B),
`fastq_overrepresented.csv` (33 B) and `fastq_gc_distribution.csv` (1,460 B).

## Oracles

| oracle | scope | result |
|---|---|---|
| base R (independent parser and counter) | duplication levels, over-representation, GC histogram and summary | exact counts (max abs 0), mean/sd within 1e-5 of printed values |
| FastQC 0.12.1 | duplication level shape and absence of over-represented reads | same shape; deduplicated 98.689% differs because FastQC subsamples internally |

FastQC's internal subsampling means its deduplicated percentage cannot match a
full-pass count; it is recorded as a sanity check only, not as a numeric pass
criterion.

## Limitations

- GC is computed per read from the whole read, not from a quality-filtered
  region.
- Over-representation uses exact sequence identity and an optional adapter list;
  no k-mer based clustering.
- The duplication table is global, so PCR duplicates and biological duplicates
  cannot be separated.
