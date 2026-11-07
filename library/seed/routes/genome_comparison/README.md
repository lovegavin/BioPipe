# Genome comparison (K-12 vs O157:H7)

Whole-genome alignment of two bacterial assemblies with `minimap2`, followed by
synteny block chaining and a rearrangement summary. The route answers three
questions: how much of each genome aligns, in which order the aligned blocks
occur, and where the order or strand changes.

## Data

| Role | File | Size | SHA256 |
| --- | --- | --- | --- |
| Reference | `k12.fasta` (NC_000913.3, *E. coli* K-12 MG1655) | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |
| Query | `o157.fasta` (NC_002695.2 chromosome + plasmids, *E. coli* O157:H7 Sakai) | 5,664,775 B | `71c2e5c364293c9ba36fc2c7acbcaa75cd6884295fe06260ba198826a8b1ddd3` |

Both files come from NCBI RefSeq (GCF_000005845.2 and GCF_000008865.2).

## Steps

| Step | Operator | WSL time |
| --- | --- | --- |
| 1 | `genome_alignment_stats` | 1.565 s |
| 2 | `export_results` (stats) | 0.002 s |
| 3 | `genome_synteny_blocks` | 1.511 s |
| 4 | `export_results` (blocks) | 0.001 s |
| 5 | `genome_rearrangement_summary` | 1.496 s |
| 6 | `export_results` (summary) | 0.001 s |

Parameters: `preset=asm5`, `min_block=1000`, `min_identity=0`, query gap 2 kb,
reference gap 50 kb.

## Results

Alignment statistics (`genome_alignment_stats.csv`):

| Statistic | Value |
| --- | --- |
| alignments | 326 |
| aligned bp | 4,085,838 |
| query bp covered | 4,044,884 (72.30 %) |
| reference bp covered | 4,063,573 (87.55 %) |
| mean identity | 0.98465055 |
| longest alignment | 102,615 bp |
| alignment N50 | 19,873 bp |

Synteny: 120 blocks, 113 forward and 7 reverse, largest block 333,996 bp.
Rearrangement summary: 23 breakpoints, 7 inversion runs, 0 translocations,
syntenic fraction 0.997895 (aligned bp inside forward blocks / total aligned bp).

Plasmids of O157:H7 do not align to the K-12 chromosome and therefore appear as
unaligned query sequence, which is why query coverage is lower than reference
coverage.

## Oracles

1. Independent PAF recomputation (separate parser and interval union code) with
   the same `minimap2` command and filters: all five alignment statistics match
   to 5.6e-16.
2. MUMmer 3.23 `nucmer` + `show-coords -rclT`: 571 alignments, 4,451,011 aligned
   bp, weighted identity 98.0594 %. Compared with this route: aligned bp ratio
   0.918 (inside the 15 % aligner tolerance), identity gap 0.41 percentage
   points (minimap2 reports divergence over the alignment block).
3. `mash dist`: 0.0227838, i.e. ANI about 97.7 %, consistent with the 98.5 %
   alignment identity.
4. Block strand agreement against nucmer coordinates: 80 of 84 comparable
   blocks (95.2 %) have the same orientation.

## Limits

- `minimap2` `asm5` is tuned for closely related assemblies; more distant
  genomes need `asm10`/`asm20` and will produce different coverage.
- Identity is `1 - de` from the PAF `de` tag (alignment-block divergence), not a
  base-level identity over the whole genome.
- Block chaining is a heuristic: 2 kb query gap, 50 kb reference gap. Small
  local rearrangements inside a block are not reported.
- Multi-copy repeats and plasmid-chromosome cross-alignments are chained as
  separate blocks; the summary does not attempt to resolve copy number.
