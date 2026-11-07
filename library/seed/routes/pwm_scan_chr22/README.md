# PWM scanning of a CTCF motif on human chr22

## Data

| Input | Source | Size | SHA256 |
| --- | --- | --- | --- |
| `input/counts.csv` | JASPAR MA0139.1 (CTCF) position frequency matrix, 19 positions, 17,310 sites (A/C/G/T counts) | 571 B source | `94d7924446f0efcf5abb35a20ec3e4401764447ae8ed44918c9e5cf3353f839c` |
| `input/chr22_200kb.fasta` | 1000 Genomes GRCh37 chr22:23,000,000-23,200,000 (200,000 bp, no N) | 203,606 B | `b2b82d4315f9f28ef6d16d9016be98cbcc023113055c2807181411c0e5fe363e` |

The window is the densest 200 kb bin of GM12878 CTCF IDR peaks on chr22
(17 peaks in window, ENCODE ENCSR000AKB / ENCFF002CDP, hg19).

## Route

1. `pwm_from_counts` - PFM to log-odds PWM (pseudocount 0.5, uniform background).
2. `export_results` - `pwm.csv`.
3. `pwm_information` - per-position information content and consensus probability.
4. `export_results` - `pwm_information.csv`.
5. `pwm_scan` - both strands, minimum score 8.0, 68 hits.
6. `export_results` - `pwm_hits.csv`.

## Results

- Consensus `TGGCCACCAGGGGGCGCTA`, total information 17.0983 bits.
- 68 hits; best score 24.6903 at position 53,381 (+, window coordinate).

## Oracles

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| Biopython `motifs` | 1.88 | PWM scores / information content / hit set | max abs 4.57e-07 / 6.67e-08; 68 vs 68 hits, 0 unique; best identical |
| base R implementation | 4.3.3 | Hit set / scores | 68 vs 68, nothing unique, max abs 7.64e-07 |
| ENCODE GM12878 CTCF peaks | ENCFF002CDP | Fraction of hits inside IDR peaks | 19/68 = 27.94% vs 3.42% random (5,000 draws, seed 7) = 8.17x |
| ENCODE GM12878 ATAC peaks | B8 route peaks | Fraction of hits inside peaks | 8.82% vs 4.08% random = 2.16x |

## Limitations

- One motif (CTCF) and one 200 kb window; not a genome-wide scan.
- Background and pseudocount are uniform (0.5), matching the oracle convention.
- The random baseline is a 5,000-draw Monte Carlo with a fixed seed.
- MOODS-python was tried as a third oracle but returned no hits at 1.0-10.0
  thresholds with the same matrix orientation, so it is not used.
