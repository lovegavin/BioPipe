# GM12878 interval annotation

Annotate ENCODE GM12878 ATAC peaks against a refGene-derived feature hierarchy,
measure how much of every feature class the peaks cover, and compare the IDR
peak set with the rep1 peak set.

## Inputs

| Source | File | Size | SHA256 | Records |
| --- | --- | --- | --- | --- |
| IDR peaks | `input/peaks.bed` | 9,819,405 B | `d3312c42b0cc241d25b56fd032b026039388d7e3cfe4a1c8457b84a7b49d6fb9` | 155,153 |
| Feature classes | `input/features.bed` | 15,479,361 B | `32cd7272ca283b67785ddc2f5acdc00d3b7f795e1aa2f791f7e793588f3b685e` | 520,033 |
| rep1 peaks | `input/rep1.bed.gz` | 2,427,146 B | `d54b59dfd4efbc3459e6e14bb9fdc45df5927c94f9ac428be517b83e0fbb9979` | 107,121 |

`features.bed` is built from UCSC hg38 `refGene.txt.gz` (8,668,756 B): each
transcript contributes a strand-aware promoter (TSS +/- 1 kb), 5' UTR, CDS,
3' UTR, exons and introns; intervals of the same class are merged with
`bedtools merge` and the class name is kept in column 4. Merged rows:
promoter 29,879, utr5 23,580, cds 18,764, utr3 23,547, exon 242,251,
intron 182,012.

The ENCODE accessions are ENCSR095QNB-derived: IDR peaks ENCFF945SYZ,
rep1 peaks ENCFF917REN (GRCh38).

## Route

`source peaks -> interval_annotate -> export_results`
`source features -> interval_coverage (with peaks) -> export_results`
`source rep1 + peaks -> interval_jaccard -> export_results`

Annotation priority is promoter, utr5, cds, utr3, exon, intron; a peak with no
overlap gets class index 6 (intergenic).

## Results (WSL, 71.5 s total)

Annotation: 155,153 peaks, class and overlap length identical to the bedtools
oracle (0 mismatches).

Coverage:

| Class | Features | Feature bp | Covered bp | Fraction | Covered features |
| --- | --- | --- | --- | --- | --- |
| promoter | 29,879 | 33,532,013 | 8,641,127 | 0.257698 | 13,910 |
| utr5 | 23,580 | 439,521,297 | 14,196,925 | 0.032301 | 14,544 |
| cds | 18,764 | 1,013,121,551 | 21,447,983 | 0.021170 | 12,000 |
| utr3 | 23,547 | 232,996,937 | 5,252,568 | 0.022544 | 4,522 |
| exon | 242,251 | 88,190,761 | 6,212,941 | 0.070449 | 24,706 |
| intron | 182,012 | 1,302,227,186 | 28,230,794 | 0.021679 | 31,004 |

Jaccard (rep1 vs IDR): intersection 38,126,042 bp, union 54,681,989 bp,
Jaccard 0.6972321727, 123,851 IDR peaks overlapping rep1 (0.707052) and
105,924 rep1 peaks overlapping IDR (0.980470).

## Oracles

`bedtools 2.31.1` (Ubuntu) is the independent implementation:

- annotation: six merged class interval sets, priority sweep, all 155,153
  peaks and overlap lengths identical.
- coverage: per-class `bedtools coverage` against the same peak BED; covered
  bp, feature counts and covered-feature counts match for all six classes.
- Jaccard: `bedtools jaccard` on merged interval sets; intersection, union and
  Jaccard identical (the tool prints 0.697232 at six decimals).

## Limits

- Only primary chromosomes chr1-22, X and Y are used; alternative contigs are
  dropped when building the feature BED.
- Coverage is measured over merged class intervals, so overlapping transcripts
  of the same class are counted once.
- Jaccard uses merged intervals; it does not model multi-mapping or peak
  confidence.
- Annotation reports the first class in the priority list and does not split a
  peak across classes.
