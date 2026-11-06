# K-12 and O157 genome k-mer comparison

Exact canonical 21-mer spectra, Jaccard containment and Mash distance between
two complete bacterial genomes, computed with the `genome_kmer_spectrum`,
`genome_kmer_similarity` and `genome_mash_distance` operators.

## Data

| Source | File | Size | SHA256 |
| --- | --- | --- | --- |
| *E. coli* K-12 MG1655, NCBI `GCF_000005845.2` | `input/ecoli.fasta` | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |
| *E. coli* O157:H7 Sakai, NCBI `GCF_000008865.2` | `input/o157.fna` | 5,664,775 B | `71c2e5c364293c9ba36fc2c7acbcaa75cd6884295fe06260ba198826a8b1ddd3` |

Both are public NCBI RefSeq assemblies. K-12 is a single chromosome; the O157
assembly contains a chromosome and plasmids, and all records are processed.

## Route

`FastaReader` sources feed six steps:

1. `genome_kmer_spectrum` (k=21, max_frequency=50) → `kmer_spectrum.csv`
2. `genome_kmer_similarity` (k=21) → `kmer_similarity.csv`
3. `genome_mash_distance` (k=21) → `mash_distance.csv`

## Results

| Statistic | Value |
| --- | --- |
| K-12 distinct canonical 21-mers | 4,543,891 |
| K-12 total 21-mer occurrences | 4,641,632 |
| O157 distinct canonical 21-mers | 5,302,382 |
| Shared 21-mers | 3,064,483 |
| Union | 6,781,790 |
| Jaccard | 0.4518693442291784 |
| Mash distance | 0.0225746167074651 |
| ANI | 0.9774253832925349 |
| Spectrum multiplicities observed | 37 (1–50 plus a 50+ overflow bucket holding 15 k-mers) |

Runtime on the development host: 1.317 s (spectrum), 2.282 s (similarity),
2.285 s (Mash distance), 6/6 steps complete.

## Oracles

| Oracle | Version | Command | Agreement |
| --- | --- | --- | --- |
| jellyfish | 2.3.1 | `jellyfish count -m 21 -C`, `jellyfish dump -c` | distinct counts, occurrence total and every spectrum bucket identical (`n_kmers` max abs diff 0.0, fraction 9.6e-17) |
| jellyfish | 2.3.1 | `jellyfish dump -c | awk '{print $1}'` set intersection | shared 3,064,483, union 6,781,790, Jaccard 0.4518693442291784 exactly |
| Mash distance formula | — | `-ln(2j/(1+j))/k` on the exact Jaccard | distance 0.0225746167074651, ANI diff 1.1e-16 |
| mash CLI | 2.3 | `mash dist -k 21 -s 1000000` | MinHash estimate 0.0225412 (Δ 3.34e-5 vs exact), reported as an approximation check, not as an exact oracle |

The jellyfish spectrum and set comparisons are independent implementations of
canonical k-mer counting; the exact Mash distance is derived from the Jaccard
index with the published mash formula.

## Limits

- Mash distance and ANI here are alignment-free and computed from the exact
  Jaccard index, so they differ slightly from sketch-based `mash dist`.
- `k` is restricted to 3–31 (2-bit encoding); k-mers containing anything other
  than A/C/G/T break the window.
- The spectrum table lists only multiplicities that occur, plus a `50+` bucket;
  consumers comparing against dense histograms must fill absent buckets with 0.
- CpG or strand-specific analyses are out of scope: k-mers are canonicalised.
