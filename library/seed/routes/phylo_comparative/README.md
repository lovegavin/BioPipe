# Phylogenetic signal and ancestral states

## Data

- `input/ssu_aligned.fasta` - Rfam RF00177 (SSU rRNA) seed alignment, 24 sequences,
  1,980 columns (48,899 B,
  sha256 `6df770ce70b0e6e6dac180266929c5f61d2929cb93c846fc4809d18945772c44`).
- `input/gc_content.csv` - GC content per sequence, `(G + C) / (A + C + G + T)`
  over the aligned columns (24 rows, column `gc`).

## Route

1. `phylo_distance_matrix` - JC69 distance matrix from the alignment.
2. `phylo_neighbor_joining` - neighbor-joining tree (24 tips, 47 nodes).
3. `phylo_lambda` - Pagel's lambda by maximum likelihood on the tree and GC content.
4. `phylo_contrasts` - Felsenstein independent contrasts (contrast and contrast variance).
5. `phylo_ancestral` - REML ancestral states for the 23 internal nodes.

The three analysis outputs are written with `export_results` (CSV).

## Results

- Pagel's lambda `0.9999999849`, log-likelihood `45.219250`, log-likelihood at
  lambda = 0 `42.544271`, likelihood ratio `5.349958`, p-value `0.010361`
  (24 tips, 47 nodes).
- 23 independent contrasts; 23 ancestral estimates (0.657-0.711) with standard
  errors 0.029-0.133.

## Oracle

Independent R implementation (`ape` 5.8.1, profile likelihood for lambda,
`ape::pic` with `var.contrasts = TRUE`, `ape::ace(method = "REML")`):

| quantity | max abs difference |
| --- | --- |
| lambda | 6.86e-11 |
| log-likelihood | 1.69e-9 |
| log-likelihood at lambda = 0 | 1.23e-9 |
| p-value | 5.93e-12 |
| PIC standardized contrast (absolute values) | 2.00e-11 |
| PIC contrast variance | 4.81e-11 |
| ancestral estimate | 8.68e-8 |

Contrast signs depend on child order, so contrasts are compared on absolute
values. `variance` is the variance of the raw contrast (`v1 + v2`), matching
`ape::pic(var.contrasts = TRUE)`; the node variance `v1*v2/(v1+v2)` is used only
internally for the upward pass.

## Limitations

- `phylo_contrasts` requires a fully binary tree.
- `phylo_lambda` optimizes lambda on `[0, 1]`; a boundary estimate means the
  trait is close to Brownian motion (lambda = 1) or to a star phylogeny
  (lambda = 0).
- REML ancestral states assume Brownian motion; standard errors are reported
  from the same model and are not independently validated.
