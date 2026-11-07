# liftOver intervals and variants

Lift BED intervals and VCF records from hg19 to hg38 with a UCSC chain file,
and summarise how much of each target chromosome the chain covers.

## Data

| Input | Size | SHA256 |
| --- | --- | --- |
| `input/intervals.bed` (500 chr22 intervals from the 1000 Genomes truth VCF) | 10500 B | `b8fa22c598cde0b7db5553f3a238e6b910ca55f95f7a2ce0d8f821a2185806f1` |
| `input/truth.vcf.gz` (GIAB HG001 chr22 truth, 846 records) | 30805 B | `3479819a02009dca99eac878a6280bd674c27c829c4c44f8830e49e484a457f8` |
| `input/hg19ToHg38.over.chain.gz` (UCSC hg19 to hg38) | 227698 B | `5c0598e500ceb5a78c73086929e8ef993aec309bcafb595139b53d440b125a1d` |

The chain file holds 1,278 chains over 93 target chromosomes.

## Route

1. `liftover_intervals`: BED + chain -> mapped and unmapped BED.
2. `liftover_variants`: VCF + chain -> mapped and unmapped VCF.
3. `chain_coverage_summary`: chain -> per-chromosome coverage table.

## Results

- Intervals: 500 of 500 mapped.
- Variants: 806 of 846 mapped, 40 unmapped, 0 alleles reverse-complemented.
- Chain coverage: 1,278 chains, 93 chromosomes, 2,896,953,941 covered bases.

## Oracles

| Check | Oracle | Result |
| --- | --- | --- |
| Mapped interval rows | CrossMap 0.7.3 (bx-python chain parser) | 500/500 identical after sorting |
| Mapped variant positions | CrossMap 0.7.3 | 806/806 operator positions present; CrossMap adds 8 boundary indels |
| Chain coverage | Independent chain-block merge | identical |

The 8 extra CrossMap records are indels whose REF spans a chain block
boundary: the anchor base maps, but the full REF is not contiguous in the
target. This operator keeps them unmapped rather than emitting an ambiguous
allele; the difference is a deliberate strictness, not a mapping error.

## Limits

- Mapping is one-to-many unaware: when a source base maps through several
  chains the first chain in file order wins.
- Variants are lifted only when the whole REF span maps contiguously on one
  target chromosome and strand; boundary indels stay unmapped.
- The chain file must use the same chromosome naming style as the inputs; the
  operator resolves a missing or extra `chr` prefix.
