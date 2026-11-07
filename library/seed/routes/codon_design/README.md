# Codon design for E. coli proteins

This route designs synonymous coding sequences for a set of *E. coli* K-12
proteins, then harmonises their GC content and reports sequence quality.

## Data

| File | Size (bytes) | SHA-256 |
| --- | --- | --- |
| `design_proteins.faa` | 4,564 | `9d19546af4f921fa09d1d4b069e1304e51b2e18028a163e8fb91deabe56f1a8e` |
| `reference.fasta` | 4,043,037 | `582ca052cc8bb43dc0bc5d88da6d8d7ff7b400308a5830e4cad1f7c7bca9c79f` |

`design_proteins.faa` contains 20 reviewed K-12 proteins without ambiguous
residues. `reference.fasta` contains the K-12 coding sequences
(`GCF_000005845.2`, CDS from genomic FASTA); 4,309 sequences pass the length,
frame, alphabet and internal-stop filters and supply the codon usage weights.
The inputs come from the public NCBI RefSeq assembly and are redistributed
unmodified.

## Steps

1. `codon_optimize` — choose, for each amino acid, the highest-usage synonymous
   codon that keeps the sequence free of the configured restriction motifs and
   homopolymer runs; report CAI, GC and forbidden-site counts.
2. `export_results` — write the optimised DNA FASTA.
3. `codon_design_qc` — measure the optimised sequences.
4. `export_results` — write the QC table.
5. `codon_gc_harmonize` — apply synonymous swaps that move each sequence toward
   50% GC without breaking the motif or homopolymer constraints.
6. `export_results` — write the harmonised DNA FASTA.
7. `codon_design_qc` — measure the harmonised sequences.
8. `export_results` — write the harmonised QC table.

## Results

All 20 designed sequences start with ATG, contain no internal stop codon and
translate to the input proteins.

| Metric | Optimised | Harmonised |
| --- | --- | --- |
| GC range | 0.5018–0.5928 | 0.5018–0.5050 |
| Mean CAI | 0.9591 | 0.9542 |
| Maximum homopolymer | 6 | 6 |
| Forbidden sites | 0 | 0 |

Exported files (WSL run, byte-identical on Linux hosts):

| File | Size (bytes) | MD5 |
| --- | --- | --- |
| `codon_optimize_dna.fasta` | 13,283 | `9f67d9fdafb6d9706a79ce8113843419` |
| `codon_gc_harmonize_dna.fasta` | 13,283 | `7a7d942a5b155b6336d36721c97dd14e` |
| `codon_design_qc_optimized.csv` | 1,368 | `50f8054da6c08bc80f616798eebad6b9` |
| `codon_design_qc_harmonized.csv` | 1,369 | `df3de719c51a921b9744cc3626d0a3e9` |

## Oracle comparison

Two independent implementations recompute CAI, GC, forbidden sites and the
translated protein from the exported FASTA:

| Oracle | Result |
| --- | --- |
| Biopython 1.88 `CodonAdaptationIndex` | CAI max abs 1.11e-16, GC max abs 0, forbidden mismatches 0, protein mismatches 0 |
| base R 4.3.3 (independent parser and formulas) | CAI max abs 0, GC max abs 0, forbidden mismatches 0 |

Both oracles agree with the operator on all 20 sequences.

## Limits

- Codon choice is greedy by reference usage; it is not a global optimum and
  does not model tRNA pools or mRNA structure.
- Only the 20 standard amino acids are accepted; selenocysteine and
  pyrrolysine sequences are rejected.
- The motif panel is a fixed default list of common restriction sites and can
  be replaced through parameters.
- GC bounds may be unreachable when every synonymous choice introduces a motif;
  the operator then reports the best sequence it can find rather than failing.
