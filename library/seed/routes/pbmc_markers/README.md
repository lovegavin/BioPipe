# PBMC3k marker genes

Cluster-versus-rest differential expression on the 10x PBMC3k subset used by the
single-cell trajectory route: 1,200 cells, 300 highly variable genes and 13
Leiden clusters.

## Inputs

| File | Bytes | Rows |
| --- | ---: | ---: |
| `input/expression.csv` | 2,542,469 | 1,200 cells x 300 genes |
| `input/clusters.csv` | 23,095 | 1,200 cells |

Inputs were prepared by the companion single-cell route: log-normalised
expression (scale factor 10,000, log1p) and Leiden clusters at resolution 1.0.
The CSV files are not shipped with the operator library.

## Steps

1. `sc_rank_genes` - Wilcoxon rank-sum for every cluster against the rest, BH
   adjustment, top 50 genes per cluster.
2. `export_results` - `sc_rank_genes.csv`.
3. `sc_marker_specificity` - tau specificity and detection rates per gene.
4. `export_results` - `sc_marker_specificity.csv`.
5. `sc_cluster_profile` - mean expression and detection fraction per cluster
   and gene.
6. `export_results` - `sc_cluster_profile.csv`.

## Results

`sc_rank_genes.csv` holds 650 rows (13 clusters x top 50), `sc_marker_specificity.csv`
300 genes, `sc_cluster_profile.csv` 3900 cluster-gene rows.

| Gene | Top cluster | Tau | Max mean |
| --- | ---: | ---: | ---: |
| GP9 | 11 | 1.0000 | 1.381 |
| RP11-211G3.2 | 10 | 1.0000 | 0.016 |
| TRPM4 | 10 | 1.0000 | 0.018 |
| ARVCF | 10 | 1.0000 | 0.006 |
| CLDN5 | 11 | 1.0000 | 0.845 |

## Oracles

Compared against SciPy 1.x `mannwhitneyu(method="asymptotic", use_continuity=False)`,
statsmodels BH and direct pandas means:

| Check | Rows | Max abs difference |
| --- | ---: | ---: |
| Wilcoxon p-value | 650 | 1.7e-16 |
| BH adjusted p | 650 | 0.0 |
| log2 fold change | 650 | 3.6e-15 |
| Cluster and rest means | 650 | 1.8e-15 |
| Tau specificity | 300 | 1.1e-16 |
| Top cluster | 300 | 0 mismatches |
| Detection fraction | 300 | 9.7e-17 |
| Cluster profile mean | 3,900 | 4.4e-16 |
| Cluster profile detection | 3,900 | 9.7e-17 |

The oracle recomputes each statistic from the same inputs; ties use the same
variance correction as SciPy.

## Limits

- The rank test is asymptotic; very small clusters should use an exact test.
- `top_cluster` is the integer position in the sorted cluster list.
- Detection counts values strictly greater than zero after log-normalisation.
- The route memory budget is enabled; the matrix is small enough for one node.
