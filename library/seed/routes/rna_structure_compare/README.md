# RNA secondary-structure comparison

Compare and summarise the secondary structures of 20 *E. coli* K-12 tRNAs.

## Input data

| File | Size | SHA-256 | Source |
| --- | --- | --- | --- |
| `trna.fasta` | 1,808 B | `94aa385024b0883cc6efc454162bffddc385926ac538cdf782b2e94b02638304` | first 20 intron-free tRNAs from `tRNAscan-SE` on the *E. coli* K-12 genome (87 tRNAs detected) |

Sequences are 75-76 nt and use `U`.

## Steps

| # | Operator | Description |
| --- | --- | --- |
| 1 | `rna_structure_distance` | Fold each tRNA with ViennaRNA `RNAfold` at 37 °C and 50 °C, pair the structures and report base-pair and Hamming distances |
| 2 | `export_results` | Export the distance table |
| 3 | `rna_structure_features` | Count pairs, stems, maximum stem length, hairpins, bulges, internal loops, multiloops, stacked pairs and unpaired positions at 37 °C |
| 4 | `export_results` | Export the feature table |
| 5 | `rna_structure_consensus` | Enumerate suboptimal structures within 3 kcal/mol with `RNAsubopt`, keep pairs above probability 0.5 and build a non-crossing consensus |
| 6 | `export_results` | Export the consensus table |

## Results (WSL, 0.3889 s)

* 12 of 20 tRNAs change structure between 37 °C and 50 °C; mean base-pair distance 3.1 (max 23), mean Hamming distance 4.65 (max 28).
* Mean number of base pairs at 37 °C is 23.6; every tRNA has a single multiloop-free cloverleaf fold.
* The consensus keeps a mean of 22 pairs with mean coverage 0.599; the largest Hamming distance between the consensus and the minimum-free-energy structure is 29.

## Oracle

The metrics are compared with an independent base-R implementation (`oracle.R`) that parses dot-bracket strings itself, builds pair sets, classifies loops from direct child pairs and greedily assembles the consensus. Over all 20 tRNAs:

| Metric | Maximum absolute difference |
| --- | --- |
| base-pair distance | 0.0 |
| Hamming distance | 0.0 |
| nine feature counts | 0.0 for every feature |
| consensus pairs / coverage / Hamming to MFE | 0.0 |
| mean pair probability | 2.9e-8 (float32 storage of the reported value) |

`RNAdistance` 2.5.1 was also probed; its `-Dh` value is a structure distance rather than the literal dot-bracket Hamming distance, so it is not used as a Hamming oracle.

## Tools

ViennaRNA 2.5.1 (`RNAfold`, `RNAsubopt`), R 4.3.3 (oracle only).

## Limitations

* One minimum-free-energy structure per temperature; the distance operator compares exactly those two structures.
* Pseudoknots are not represented; only nested dot-bracket structures are accepted.
* Consensus assembly is greedy and non-crossing; a different tie order could choose another equally supported pair set.
* Fixed default temperatures and energy window; both are parameters.
