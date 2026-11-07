# Hi-C pair QC (GM12878 MboI, hg19)

## Data

| File | Source | Size | SHA-256 |
|---|---|---|---|
| `gm12878.pairs.gz` | open2c/cooler test data, GM12878 MboI, hg19 (`hg19.GM12878-MboI.pairs.subsample.sorted.txt.gz`) | 1,066,265 B | `909637e9f061583a2d9be9273f03e87ab448c251d1ebabb3bf7fa66dcd59fa0a` |
| `hg19.chrom_sizes.txt` | chromosome sizes from the same cooler test dataset | 376 B | `996a373585807b82f1ff0919f3a37b0e3c674d904efd41e16a202630faf91405` |

The pairs file holds 100,000 pairs (76,888 cis, 23,112 trans) in 6-column pairs format.

## Route

`task.yaml` reads `input/gm12878.pairs.gz` (PairsReader) and
`input/hg19.chrom_sizes.txt` (TsvFileReader) and runs six steps:

1. `hic_pair_stats` -> `hic_pair_stats.csv`
2. `export_results` (csv)
3. `hic_contact_matrix` (chr1, 1 Mb) -> `hic_contacts_chr1.csv`
4. `export_results` (csv)
5. `hic_distance_decay` (20 bins) -> `hic_decay.csv`
6. `export_results` (csv)

## Results

- Pair stats: total 100,000; cis 76,888; trans 23,112; cis fraction 0.76888;
  25 chromosomes; mean cis distance 7,192,061.143338 bp (step 0.07 s).
- Contact matrix: chr1 at 1 Mb, 2,123 contact bins, 6,830 pairs; diagonal
  contacts (start1 == start2) are retained (4,056 pairs).
- Distance decay: 20 bins, 18 non-empty, 2,774 non-diagonal pairs; first bin
  1,000,000-1,316,344 bp has 219 bins and 838 pairs (mean 3.826).
- Whole route: 0.14 s of step time, ~0.87 s wall, 98 MB peak RSS.

## Independent oracles

| Oracle | Check | Result |
|---|---|---|
| R 4.3.3 base (independent parser + binning) | pair stats vs operator | total/cis/trans/cis fraction/mean distance identical (mean 7,192,061.143338) and 25 chromosomes |
| R 4.3.3 base | chr1 1 Mb matrix | 2,123 rows in both, 0 only-ours, 0 only-oracle, 0 count mismatches, sum 6,830 |
| R 4.3.3 base | decay bins | 20 bins, max abs difference 0 for n_contacts, n_pairs, mean_count and fraction |
| cooler 0.10.4 (`cload pairs` + `dump --join`) | chr1 1 Mb matrix | 2,123 rows in both, 0 count mismatches, sum 6,830 |
| cooler 0.10.4 (decay recomputed from the cooler matrix) | decay bins | max abs difference 0 for all four statistics |

`pairtools stats` could not be used: the six-column test file carries no
`pair_type` column, and a synthesized header still reports cis=0, so it is not
an authoritative oracle for this dataset.

## Limitations

- The pair-level QC does not perform read-level deduplication, filtering by MAPQ
  or restriction-fragment assignment: it measures exactly what the pairs file
  contains.
- `hic_contact_matrix` bins cis contacts only by default; `include_trans`
  produces chromosome-pair labels but is not used here.
- The decay curve is computed from the binned chr1 matrix (distances are bin
  starts), so the diagonal bin is excluded and counts are contacts between bins,
  not individual molecules.
- Distances are genomic (hg19), not restriction-fragment aware.
