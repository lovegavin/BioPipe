# Assembly contiguity and gap QC

Assembly-level quality control on two real public genomes: the 17-sequence
*Saccharomyces cerevisiae* S288C reference (multi-contig case) and the
single-contig *Escherichia coli* K-12 MG1655 reference (zero-gap control).

## Data

| Source | Records | Bases | SHA-256 |
| --- | --- | --- | --- |
| `input/genome.fna` — *S. cerevisiae* S288C, GCF_000146045.2 | 17 | 12,157,105 | `fe42735d3e6242f8c40b457a232940e34ef15eb4502717e54a34ed118face4c1` |
| `input/ecoli.fasta` — *E. coli* K-12 MG1655, GCF_000005845.2 | 1 | 4,641,652 | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

The yeast FASTA is the NCBI RefSeq assembly downloaded for batch 8; the E. coli
FASTA is the reference used by the batch 3 resequencing route. Exact sizes and
SHA-256 values are recorded in the verification evidence.

## Route

Ten steps:

1. `assembly_contig_stats` on the yeast assembly → `yeast_contig_stats.csv`
2. `assembly_contiguity` on that table → `yeast_contiguity.csv`
3. `assembly_gap_stats` on the yeast assembly → `yeast_gaps.csv`
4. the same three operators on the E. coli assembly (`*_stats.csv`, `*_gaps.csv`)

`assembly_contig_stats` returns per-contig `length`, `gc_fraction`,
`n_fraction` and `n_runs`; `assembly_contiguity` reduces a contig table to
`n_contigs`, `total_bp`, length distribution, `n50`/`l50`, `n90`/`l90`, `auN`
and length-weighted GC; `assembly_gap_stats` counts `N` runs per contig and
reports genome-wide gap totals.

## Results (WSL, Python 3.12, 0.79 s total)

| Metric | Yeast | E. coli |
| --- | --- | --- |
| Contigs | 17 | 1 |
| Total bp | 12,157,105 | 4,641,652 |
| Min / median / max length | 85,779 / 745,751 / 1,531,933 | 4,641,652 |
| N50 / L50 | 924,431 / 6 | 4,641,652 / 1 |
| N90 / L90 | 439,888 / 13 | 4,641,652 / 1 |
| auN | 904,609.4998 | 4,641,652 |
| GC fraction | 0.38147865 | 0.50790710 |
| Gap runs / gap bp | 0 / 0 | 0 / 0 |

## Oracles

Two independent implementations agree exactly:

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| `seqkit stats -a` | 2.9.0 | num_seqs, sum_len, min/avg/max, Q1/Q2/Q3, N50, N50_num, GC%, sum_n | all equal (GC and N50 exact; printed GC is rounded to 0.01%) |
| Biopython `SeqIO` + independent N50/gap-run code | 1.86 | per-contig lengths, n50/l50, aun, weighted GC, gap runs and gap bp | max abs diff 0.0 for every compared value |

`seqkit` fills the role of an external, independently implemented assembly
statistics tool; the Biopython script recomputes the same quantities with a
separate code path (regex gap runs, manual cumulative N50) rather than calling
the operator helpers.

## Limitations

- N/L statistics are computed over contig lengths only; scaffolds with `N`
  runs are counted at full length (gaps are reported separately).
- `auN` uses contig lengths; it is not assembly-graph aware.
- The route uses reference assemblies, so gap counts are zero by construction;
  the E. coli single-contig case is a negative control for the gap operator.
- No QUAST comparison is included in this batch; QUAST is an external tool
  wrapper already covered by the library's `assembly_stats` operator tests.
