# SSU rRNA phylogeny route

Builds a distance matrix, a neighbour-joining tree and an unrooted tree
distance from a real Rfam seed alignment. This route exercises
`phylo_distance_matrix`, `phylo_neighbor_joining` and `phylo_tree_distance`.

## Data

| Item | Value |
| --- | --- |
| Family | Rfam RF00177 (SSU_rRNA_bacteria) |
| Seed alignment | <https://rfam.org/family/RF00177/alignment> |
| Stockholm size / SHA-256 | 477,373 B / `efe8d15fab12034e79aa5c8599b1018de2ac8a98257ec0df94a1347112177276` |
| Alignment length | 1,980 columns |
| Seed sequences | 99 |
| Selected taxa | 24 (equal stride over gap fraction <= 0.5) |
| Route input | `input/ssu_aligned.fasta`, 48,899 B, SHA-256 `6df770ce70b0e6e6dac180266929c5f61d2929cb93c846fc4809d18945772c44` |

The seed alignment is the curated Rfam alignment; no de novo alignment is
performed by this route.

## Steps

| # | Operator | Parameters |
| --- | --- | --- |
| 1 | `phylo_distance_matrix` | `model=jc69`, `deletion=complete`, output `dm_jc69` |
| 2 | `export_results` | CSV `ssu_distance_jc69` |
| 3 | `phylo_neighbor_joining` | output `tree_jc69` |
| 4 | `export_results` | Newick `ssu_nj_jc69` |
| 5 | `export_results` | CSV `ssu_nj_jc69_nodes` |
| 6 | `phylo_distance_matrix` | `model=p`, `deletion=complete`, output `dm_p` |
| 7 | `export_results` | CSV `ssu_distance_p` |
| 8 | `phylo_neighbor_joining` | output `tree_p` |
| 9 | `export_results` | Newick `ssu_nj_p` |
| 10 | `phylo_tree_distance` | `tree_jc69` vs `tree_p`, output `tree_distance` |
| 11 | `export_results` | CSV `ssu_tree_distance` |

## Results (WSL, 11/11 steps, ~1.1 s)

- Complete deletion keeps 1,396 of 1,980 columns over 24 taxa.
- `ssu_distance_jc69.csv` is a full 24 x 24 symmetric matrix (12,023 B).
- `ssu_nj_jc69.nwk` / `ssu_nj_p.nwk` are rooted bifurcating Newick trees
  with 24 tips (1,243 B / 1,258 B).
- `ssu_tree_distance.csv`: `rf=14`, `max_rf=42`, `normalized_rf=0.333333`,
  `shared_splits=14`, `splits_a=splits_b=21`, `branch_score=0.02463759`,
  `identical=0`.

## Oracles

| Oracle | Version | Check | Result |
| --- | --- | --- | --- |
| Biopython `DistanceCalculator("identity")` + `nj` | 1.88 | p-distance matrix vs `ssu_distance_p.csv` | max abs **5.55e-17** |
| Biopython `nj` vs `ssu_nj_p.nwk` | 1.88 | unrooted splits | RF **0**, 21/21 shared |
| Biopython branch lengths | 1.88 | split branch lengths (root edge summed) | max abs **4.06e-12** |
| R `ape` `dist.dna(model="JC69", pairwise.deletion=FALSE)` | 5.8.1 | JC69 matrix vs `ssu_distance_jc69.csv` | max abs **0** |
| R `ape` `nj` + `dist.topo(method="PH85")` | 5.8.1 | unrooted topology | RF **0** |
| R `ape` `cophenetic` | 5.8.1 | tip-to-tip path distances | max abs **9.17e-11** |

Biopython 1.88 no longer offers a `jc69` model in `DistanceCalculator`, so
it is used for p-distances and for neighbour joining; JC69 is checked with
R `ape`, an independent implementation.

## Notes and limitations

- The operator previously narrowed the distance matrix to float32, which
  shifted p-distances by 1.5e-8 and branch lengths by 2.9e-4. The matrix is
  now kept as float64 and `tests/test_extension379.py` locks that down.
- `phylo_neighbor_joining` writes a bifurcating root, while Biopython's NJ
  root is trifurcating. The unrooted tree is identical; comparisons must
  sum the two root edge lengths.
- The route infers NJ from a curated alignment; it is not a maximum
  likelihood phylogeny and has no bootstrap support.
- 24 of 99 seed sequences are used to keep the run small; the operator
  itself accepts any number of aligned sequences (>= 3).
- RNA `U` is treated as a base; JC69 uses only the mismatch fraction, so
  the U/T distinction does not change these distances.
