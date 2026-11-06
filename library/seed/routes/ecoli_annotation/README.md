# E. coli annotation route

Window density, intergenic gaps, stranded promoters and CDS integrity for the
*Escherichia coli* K-12 MG1655 reference, driven by the RefSeq GFF3 annotation.

## Data

| Input | Source | Size | SHA256 |
|---|---|---|---|
| `input/ecoli.gff` | NCBI RefSeq `GCF_000005845.2_ASM584v2_genomic.gff.gz` (unpacked, 9,531 lines) | 2,314,238 B | `68d25735ccde6d37af68613dca57a588ae69423f0ecee99b0f29d596eff7accb` |
| `input/ecoli.fasta` | NCBI RefSeq `GCF_000005845.2_ASM584v2_genomic.fna.gz` (unpacked, `NC_000913.3`) | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

Oracle-only input: `GCF_000005845.2_ASM584v2_protein.faa.gz` (902,395 B).

## Steps

1. `genome_gene_density` — 10 kb windows, gene features → `gene_density.csv`
2. `genome_intergenic_regions` — complement of merged gene intervals → `intergenic_regions.csv`
3. `genome_promoter_extract` — 100 bp stranded upstream of every gene → `promoters.fasta`
4. `genome_cds_check` — CDS length/start/stop/internal-stop audit → `cds_check.csv`

Each result is exported through `export_results`; the promoter result is a
sequence Form exported as FASTA from `info.sequences`.

## Observed results

| Result | Value |
|---|---|
| Density windows | 465 (4,641,628 bp genome) |
| Intergenic gaps | 3,680 gaps, 611,155 bp |
| Promoters | 4,506 sequences, 100 bp each |
| CDS records | 4,340; length_ok 4,319, start_ok 4,311, stop_ok 4,319, internal stops 12 |

## Oracle checks

| Check | Independent implementation | Result |
|---|---|---|
| Density | `bedtools makewindows` + `bedtools coverage` 2.31.1 | 465/465 windows identical, 0 mismatched |
| Intergenic | `bedtools complement` 2.31.1 | 3,680 gaps and 611,155 bp identical |
| Promoters | `bedtools getfasta -s` 2.31.1 | 4,506/4,506 sequences identical |
| CDS flags | Biopython 1.88 `Seq.translate(table=11)` | 4,340/4,340 records identical |
| Protein identity | RefSeq proteome (4,259 proteins) | 4,288/4,340 CDS translate to an exact RefSeq protein |

The 52 unmatched CDS are 21 partial records (length not a multiple of three)
and 31 duplicate/alternative-frame annotations, plus selenocysteine entries
that RefSeq renders with `U`.

## Limits

- Promoters are derived from GFF `gene` features only: no operon, UTR or
  transcription-start information is available in this input.
- Upstream windows are clipped at contig boundaries; the promoter matrix pads
  short rows with `N` but `info.sequences` keeps the clipped string.
- CDS start codons `ATG`, `GTG` and `TTG` are accepted; internal stops are
  reported rather than treated as errors, because pseudogene fragments exist in
  the RefSeq annotation.
- Density windows start at each sequence origin; the final window of a contig
  may be shorter than the configured window.
- CDS records that share a `locus_tag` (alternative frames or split features)
  are disambiguated with `#2`, `#3` suffixes on the output axis.
