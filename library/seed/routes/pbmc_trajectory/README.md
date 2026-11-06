# PBMC3k trajectory

Trajectory and cell-cell communication operators over the 10x Genomics PBMC3k
dataset: diffusion pseudotime, PAGA connectivity, gene trends along pseudotime,
and ligand-receptor co-expression between clusters.

## Data provenance

The input is the public 10x Genomics PBMC3k filtered matrix:

```
https://cf.10xgenomics.com/samples/cell-exp/1.1.0/pbmc3k/pbmc3k_filtered_gene_bc_matrices.tar.gz
7,621,991 B
```

Preparation (scanpy 1.12.5, igraph 1.0.0, leidenalg 0.12.0):

1. `sc.read_10x_mtx` with gene symbols, keep cells with >= 200 genes and genes
   in >= 3 cells: 2,700 cells x 13,714 genes.
2. `normalize_total(target_sum=1e4)`, `log1p`.
3. 300 highly variable genes, `scale(max_value=10)`, PCA with 20 components.
4. 15-neighbour graph, Leiden at resolution 1.0: 13 clusters.
5. A fixed random subsample of 1,200 cells (`numpy.random.default_rng(0)`) keeps
   the route fast on a laptop; the seed is part of the preparation record.

The route consumes four files:

| File | Shape | Content |
| --- | --- | --- |
| `embedding.csv` | 1,200 x 20 | PCA scores, columns `PC1`..`PC20` |
| `clusters.csv` | 1,200 x 1 | Leiden cluster id (0..12) |
| `expression.csv` | 1,200 x 300 | log-normalized HVG expression |
| `communication.csv` | 1,200 x 29 | log-normalized expression of the ligand/receptor genes in `pairs.csv` |

`pairs.csv` is a 20-pair panel of canonical immune ligand-receptor interactions
(CXCL8-CXCR1/2, CCL5-CCR1/5, CD40LG-CD40, CD28-CD80/86, ICAM1-ITGAL/ITGB2,
CSF1-CSF1R, IL1B-IL1R1, TNF-TNFRSF1A, LTB-LTBR, SELL-SELPLG, CD70-CD27,
IL7-IL7R, CCL4-CCR5, CCL3-CCR1, CXCL10-CXCR3, IL2-IL2RA). It is a demonstration
panel, not a complete interaction database; the operator accepts any curated
table with `ligand,receptor` columns.

## Route

```
pseudotime_dpt -> export_results
paga_connectivity -> export_results
trajectory_gene_trends -> export_results
cell_communication -> export_results
```

The root cell is `AAACATACAACCAC-1`, the first barcode of the filtered matrix.
DPT direction is defined by that choice: a different root yields the same
ordering up to reversal, which is why the verification compares rank
correlation rather than absolute values.

## Oracles

Measured on the 1,200 x 20 embedding with scanpy 1.12.5, anndata 0.13.4 and
NumPy 2.1.3 (`workdir/b4_oracle.json`):

| Operator | Oracle | Result |
| --- | --- | --- |
| `pseudotime_dpt` | scanpy `sc.pp.neighbors(method="gauss")` + `sc.tl.diffmap` + `sc.tl.dpt` with the same root | Spearman **0.9507**, Pearson 0.5883, max abs 0.5915 |
| `paga_connectivity` | scanpy `sc.tl.paga` with the same neighbours and clusters | Pearson **0.9635**, max abs 0.4381 after max-scaling |
| `trajectory_gene_trends` | independent pandas groupby over the same bin edges | max abs **9.9e-17**, identical NaN mask |
| `cell_communication` | independent pandas per-cluster means and the same product formula | **734/734** interactions, 0 missing, 0 extra, max abs **2.2e-16** |

Pseudotime is an ordinal quantity: the rank correlation is the meaningful
agreement measure and the absolute values differ because the operator builds an
adaptive kNN graph symmetric by maximum while scanpy builds a Gaussian kernel
graph; both use the Haghverdi et al. (2016) lambda/(1-lambda) component weights.
PAGA connectivities are normalised differently (our off-diagonal maximum is 1),
so the two matrices are compared after the same scaling.

There is no external authoritative command-line tool for pseudotime or
communication scores on this dataset; the scanpy implementations are independent
codebases, and the two pandas recomputations check the arithmetic directly.

## Limitations

- `pseudotime_dpt` only uses the supplied embedding; it does not normalize,
  select genes or compute the embedding itself.
- `paga_connectivity` is a normalized kNN edge count, not a statistical test.
- `trajectory_gene_trends` reports the mean expression in equal-width
  pseudotime bins; an empty bin is `NaN`.
- `cell_communication` scores co-expression of a ligand in one cluster and its
  receptor in another; it is not a permutation test and does not model
  complexes or secreted diffusion.
- The 1,200-cell subsample is a runtime compromise; all cells can be used by
  changing the preparation seed and size.
