# Primer design and specificity

End-to-end primer workflow on the *Escherichia coli* K-12 MG1655 genome:
Tm estimation with nearest-neighbour thermodynamics, PCR primer pair design
around five housekeeping targets, and in-silico specificity of one designed
pair against the whole genome.

## Data

| Role | File | Size | SHA-256 |
| --- | --- | --- | --- |
| Template and specificity genome | `input/ecoli.fasta` | 4699745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |
| Tm probes | `input/oligos.fasta` | 6 oligos (18-25 nt) | derived from genome windows |
| Specificity pair | `input/pair_dnaA.fasta` | dnaA pair 1 (forward + reverse) | derived from genome |

Source: *E. coli* K-12 MG1655 reference genome (NCBI RefSeq
`GCF_000005845.2`), the same assembly used by the annotation and
resequencing routes. Tm probes and the specificity pair are exact
substrings of that assembly, so all coordinates in this route are
reproducible from the FASTA file alone.

## Steps (14)

1. `primer_tm` over `oligos.fasta` (SantaLucia 1998, 50 mM Na+, 25 nM
   strands) -> `export_results` (`oligo_tm.csv`).
2. Five branches, one per target (`lacZ` 363800-363899, `gyrA`
   2337200-2337299, `recA` 2823000-2823099, `dnaA` 3882800-3882899,
   `thrA` 800-899): `primer_design` (flank 250, 18-24 nt, Tm 57-63 C,
   GC 40-60%, product 120-320 bp, 5 pairs) -> `export_results`
   (`pairs_<target>.csv`).
3. `primer_specificity` for dnaA pair 1 against the whole genome (both
   strands, 0 mismatches, product 100-1000 bp) -> `export_results`
   (`amplicons.csv`).

## Results

| Probe | Length | GC | Tm (C) |
| --- | --- | --- | --- |
| oligo1 | 20 | 0.600 | 60.041530 |
| oligo2 | 22 | 0.636 | 61.362942 |
| oligo3 | 18 | 0.500 | 51.023410 |
| oligo4 | 25 | 0.440 | 55.848580 |
| oligo5 | 20 | 0.700 | 62.183404 |
| oligo6 | 19 | 0.474 | 48.475429 |

First designed pair per target (all pairs satisfy the constraints):

| Target | Left (1-based) | Right (1-based) | Tm left/right (C) | Product |
| --- | --- | --- | --- | --- |
| lacZ | 363795-363818 | 363922-363945 | 59.707 / 59.828 | 151 |
| gyrA | 2337179-2337199 | 2337305-2337327 | 59.713 / 59.996 | 149 |
| recA | 2822995-2823020 | 2823117-2823140 | 59.319 / 59.692 | 145 |
| dnaA | 3882782-3882805 | 3882912-3882935 | 59.715 / 58.881 | 154 |
| thrA | 791-814 | 918-941 | 60.055 / 59.526 | 151 |

Specificity for the dnaA pair: exactly one amplicon, `NC_000913.3`
3882782-3882935 (154 bp, plus strand, 0 mismatches on both primers).

## Independent oracles

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| Biopython `MeltingTemp.Tm_NN` (SantaLucia 1998) | 1.8x | 6 probe Tm values | max abs difference 0.0 C |
| EMBOSS `oligotm` (`-mv 50 -dv 0 -n 0`, default 50 nM strands) | 6.6.0 | 6 probes + 10 designed primers | max abs difference 4.99e-07 C (6-decimal output) |
| `primer3_core` design with the same target and constraints | 2.6.1 | 5 targets | 5/5 targets returned 5 valid pairs each; every picked pair is inside Tm 57-63 C and product 120-320 bp |
| `bwa mem -k 12 -T 0 -a` exact 24M alignments | 0.7.17 | dnaA pair against the genome | one product 3882782-3882935 / 154 bp, identical to the operator |

The primer3 picks differ from the operator picks because the penalty
weights are not identical (primer3 optimises its own weighted score);
both sets satisfy every declared constraint, so the design operator is
validated on feasibility and Tm/GC/product bounds rather than on
selecting the same pair.

`primersearch` (EMBOSS) was probed with several input layouts but did not
report amplimers for a known positive pair, so its input format is left
unresolved; `bwa mem` is used instead as the independent specificity
oracle.

## Limits

- Tm is the SantaLucia 1998 nearest-neighbour model with 50 mM Na+,
  0 mM Mg2+, 0.25 uM strands; other salt conditions will shift Tm.
- Design enumerates primer pairs inside `target +/- flank`; very large
  flanks or dense targets increase runtime quadratically.
- Specificity is exact-match only (0 mismatches by default); set
  `max_mismatches` to allow near matches. Amplicons shorter than 100 bp
  or longer than 1000 bp are filtered by the route parameters.
- The route does not model primer-dimers, hairpins or template secondary
  structure.
