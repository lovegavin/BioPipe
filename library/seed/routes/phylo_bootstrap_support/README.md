# Bootstrap support for an SSU rRNA phylogeny

Non-parametric bootstrap support for a neighbour-joining tree built from 24
small-subunit rRNA sequences.

## Data

| Source | File | Size | SHA256 |
| --- | --- | --- | --- |
| Rfam/NCBI SSU rRNA alignment (B17) | `input/ssu_aligned.fasta` | 48,899 B | `6df770ce70b0e6e6dac180266929c5f61d2929cb93c846fc4809d18945772c44` |

The alignment has 24 sequences and 1,980 columns; 1,396 columns are complete
(no gap or ambiguous base in any sequence) and are used for JC69 distances.

## Steps

1. `phylo_distance_matrix` (JC69, complete deletion)
2. `phylo_neighbor_joining`
3. `phylo_bootstrap` (100 column resamples, seed 0)
4. export bootstrap support (CSV)
5. `phylo_support_summary` (threshold 0.5)
6. export support summary (CSV)
7. `phylo_support_filter` (collapse splits with support < 0.5)
8. export support-filtered tree (Newick)

## Results

| Quantity | Value |
| --- | --- |
| Non-trivial splits | 21 |
| Mean support | 0.3962 |
| Median support | 0.25 |
| Max support | 1.00 |
| Splits below 0.5 | 13 |
| Internal nodes after collapse | 9 |

The low mean support reflects the short, conserved SSU rRNA alignment: only
1,396 complete columns and comparatively few informative sites, so most splits
are not resolved by 100 resamples.

## Oracle

An independent R implementation (`ape` 5.8.1) parses the FASTA, computes JC69
distances with complete deletion, builds the neighbour-joining tree and runs
1,000 bootstrap replicates with its own RNG.

| Comparison | Result |
| --- | --- |
| Splits recovered (ours / R) | 21 / 21 |
| Symmetric difference | 0 |
| Mean absolute support difference | 0.0223 |
| Max absolute support difference | 0.0750 (tolerance 0.20) |

## Limitations

- Unrooted neighbour-joining topology; support is reported per bipartition.
- Only JC69 with complete deletion; no model selection or rate variation.
- Bootstrap RNG differs between implementations, so support values are compared
  with a Monte-Carlo tolerance rather than bit-for-bit.
- Both children of the root encode the same bipartition, so a low-support split
  can collapse two nodes (the operator reports `n_collapsed` nodes).
