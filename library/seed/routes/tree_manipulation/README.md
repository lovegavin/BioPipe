# Tree manipulation (midpoint rooting, tip pruning, balance)

## Input data

`input/ssu_aligned.fasta` - 24 small-subunit rRNA sequences from Rfam RF00177
(SSU rRNA), aligned to 1,980 columns. Source: Rfam seed alignment, build 14.4;
the same alignment used by `rfam_ssu_phylogeny`. SHA256
`6df770ce70b0e6e6dac180266929c5f61d2929cb93c846fc4809d18945772c44`.

`phylo_distance_matrix` with `deletion=complete` removes gap columns and leaves
1,396 sites; distances are JC69 (`mean_distance=0.2782382923563276`).

## Graph

`alignment -> phylo_distance_matrix -> phylo_neighbor_joining -> tree_root_midpoint
 -> tree_prune_tips (3 tips) -> tree_balance x2 -> 5 exports`

The neighbor-joining tree is exported as `tree_nj.nwk`, the midpoint-rooted
tree as `tree_rooted.nwk`, the pruned tree as `tree_pruned.nwk`, and the two
balance tables as CSV.

## Results

| Step | Value |
| --- | --- |
| NJ tree | 24 tips, 47 nodes, total branch length 3.0162223795294296 |
| Midpoint root | diameter 0.3868628628124091, max root-to-tip 0.19343143140620456 |
| Pruned tree | 24 -> 21 tips (3 removed), 41 nodes, total branch length 2.7598575086449273 |
| Balance (rooted) | sackin 121, colless 27, normalized 0.1067193675889328, cherries 10 |
| Balance (pruned) | sackin 101, colless 23, normalized 0.12105263157894737, cherries 8 |

Both rooted trees are strictly binary, so Colless is defined.

## Independent oracles

* dendropy 5.1.3: `treemeasure.sackin_index(..., normalize=False)`,
  `treemeasure.colless_tree_imbalance(..., normalize=None)`, and an explicit
  cherry count on `tree_rooted.nwk` / `tree_pruned.nwk`. Sackin 121/101,
  Colless 27/23, cherries 10/8 - all absolute differences 0.
* R ape 5.8.1: `dist.topo(unroot(tree_rooted.nwk), tree_nj.nwk) == 0`
  (rooting does not change the unrooted topology); the diameter computed from
  `cophenetic(tree_nj.nwk)` equals twice the maximum root-to-tip distance
  (difference 2e-12); `dist.topo(keep.tip(tree_nj.nwk, kept),
  tree_pruned.nwk) == 0` and the cophenetic distance matrices agree within
  1.27e-8 (tree branch lengths are stored as float32).

## Implementation notes

* `tree_root_midpoint` inserts a new root inside the longest tip-to-tip edge
  when the midpoint falls in the middle of an edge, then suppresses the old
  root if it becomes unary. Without suppression the tree gained a unary node
  (24 internal nodes and no Colless); the regression test asserts 23 internal
  nodes for the sample tree.
* `tree_prune_tips` removes tips, deletes internal nodes with no remaining
  children, merges unary internal nodes into their child edge, and promotes a
  single remaining child to the root. A tree reduced to one tip is allowed.
* The tree Form uses `float32` branch lengths, hence the 1e-8 cophenetic
  tolerance; topology checks are exact.

## Limits

* Tip names must match the tree labels exactly; unknown tips raise
  `tree_prune_tips: unknown tip(s)`.
* Balance statistics require a rooted tree; Colless is only reported for
  strictly binary trees.
* The midpoint root is not unique when several tip pairs share the maximum
  distance; ties are broken by the first pair in tip order.
