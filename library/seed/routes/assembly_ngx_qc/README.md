# Assembly NGx and length-profile QC

## Purpose

Compute assembly integrity metrics beyond N50/L50: NGx against an estimated
genome size, area under the Nx curve (auN/auNG), cumulative curves and contig
length bins. The route uses the *Saccharomyces cerevisiae* S288C reference
assembly (17 contigs) and the *Escherichia coli* K-12 single-contig assembly as
a degenerate control.

## Data

| file | bytes | sha256 |
|---|---|---|
| `yeast.fna` | 12,310,392 | `fe42735d3e6242f8c40b457a232940e34ef15eb4502717e54a34ed118face4c1` |
| `ecoli.fasta` | 4,699,745 | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

Yeast: 17 contigs, 12,157,105 bp. E. coli: 1 contig, 4,641,652 bp.

## Steps

1. `assembly_ngx_metrics` on `yeast` with `genome_size=12157105`.
2. `export_results` -> `assembly_ngx_metrics.csv`.
3. `assembly_ngx_curve` with `step=10`.
4. `export_results` -> `assembly_ngx_curve.csv`.
5. `assembly_length_bins` with the default bin edges.
6. `export_results` -> `assembly_length_bins.csv`.

## Results (WSL, 6/6)

| metric | value |
|---|---|
| genome size | 12,157,105 bp |
| contigs | 17 |
| N50 / NG50 | 924,431 / 924,431 bp |
| L50 | 6 |
| N90 / NG90 | 439,888 / 439,888 bp |
| auN / auNG | 904,609.499825 / 904,609.499825 |

Contig bins: 50-99 kb 1 contig, 100-249 kb 1, 250-499 kb 3, 500-999 kb 8,
>= 1 Mb 4; no contig below 50 kb.

## Oracle

| oracle | scope | result |
|---|---|---|
| QUAST 5.2.0 (`--est-ref-size 12157105`) | N50/NG50/L50/N90/auN/auNG/contigs/length | exact except auN printed to 1 decimal (delta 1.7e-4) |
| base R 4.3.3 (independent FASTA parser) | Nx curve, auN/auNG, bins, metrics | max abs 1.2e-10 |

The QUAST auN tolerance is 0.05 because its report prints one decimal; all
integer metrics are exact.

## Limitations

- NGx uses the supplied `genome_size`; passing 0 falls back to the assembly
  total, at which point NGx equals Nx.
- Length bins are fixed edges by default; custom edges must be strictly
  increasing and may end with `0` to denote an open upper bound.
- The route exercises the yeast assembly only; the E. coli control is included
  as a single-contig input for local checks.
