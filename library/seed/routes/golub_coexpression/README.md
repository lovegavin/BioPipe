# golub_coexpression

WGCNA-style co-expression network on the Golub (1999) acute leukemia cohort:
soft-threshold fit, TOM-based module detection, module eigengenes and
module-trait correlation.

## Data

| Source | Provenance | Size |
| --- | --- | --- |
| `input/expression.csv` | Golub et al. (1999) microarray data distributed as the `Golub1999.rds` ExpressionSet (IowaBiostat `golub` package, Git LFS object `de43dd8798c09a681b593c052ebf83acda9f0a691ca8e3ccd779a3a4ae0633b0`, 3,712,634 B), converted with `rdata` 0.5.2 | 4,103,343 B |
| `input/traits.csv` | `class` labels from the same ExpressionSet, AML = 1, ALL = 0 | 364 B |

72 samples (47 ALL, 25 AML) x 7,129 Affymetrix probes; rows are sample IDs
(`39`, `40`, ...) and columns are probe names. The route uses the 2,000 most
variable probes, exactly like the R oracle.

## Steps

1. `wgcna_soft_threshold` — scale-free topology fit for powers
   1-10,12,14,16,18,20 and 2,000 variable probes.
2. `coexpression_modules` — unsigned adjacency (beta = 6), TOM, average
   linkage, fixed cut at 0.99, eigengene merge at 0.75, minimum module size
   30; output is a `[feature, module]` table with `grey` = 0.
3. `module_eigengenes` — first principal component per module, z-scored and
   sign-aligned with the module mean expression.
4. `module_trait_correlation` — Pearson correlation of each eigengene with
   the AML indicator, with the two-sided t-test p value.

Every operator output is exported to CSV with `export_results`.

## Reference run (WSL)

| Step | Elapsed |
| --- | --- |
| `wgcna_soft_threshold` | 0.201 s |
| `coexpression_modules` | 0.291 s |
| `module_eigengenes` | 0.010 s |
| `module_trait_correlation` | 0.224 s |
| total | 0.734 s |

Modules: `0:1518 1:126 2:96 3:91 4:68 5:54 6:47`.

| Module | r (AML) | p |
| --- | --- | --- |
| 1 | 0.827996 | 2.95e-19 |
| 2 | -0.721153 | 9.03e-13 |
| 3 | -0.474847 | 2.50e-05 |
| 4 | 0.176259 | 1.39e-01 |
| 5 | -0.120287 | 3.14e-01 |
| 6 | 0.518194 | 3.13e-06 |

## Oracles

Independent implementation: **WGCNA 1.73** (R 4.3, conda-forge) running
`pickSoftThreshold`, `adjacency`, `TOMsimilarity`, `hclust`/`cutree` and
`mergeCloseModules` on the same 2,000 probes.

| Quantity | Max abs difference |
| --- | --- |
| `mean_k`, `median_k`, `max_k` | 1.7e-13, 1.7e-13, 4.0e-13 |
| `r_squared`, `slope` of the scale-free fit | 5.6e-16, 2.3e-14 |
| module labels (2,000 probes) | identical (2000/2000) |
| eigengene correlation with `ME1`-`ME6` | 1.0 (sign-aligned z max abs 3.1e-14) |
| trait `correlation`, `p_value` | 4.8e-15, 4.0e-13 relative |

`tests/test_extension368.py::test_scale_free_fit_matches_wgcna_reference` pins
the histogram regression against values produced by `scaleFreeFitIndex()`.

Duplicate probe names are renamed differently by pandas (`ACTB.1`) and R
`write.csv` (`ACTB.1`, `ACTB.3`, ...); the comparison therefore matches module
labels per base name, which is why the raw name-based identical fraction is
0.9957 while all 2,000 labels agree.

## Limitations

- The network is unsigned and restricted to the 2,000 most variable probes.
- `cut_height = 0.99` and `merge_threshold = 0.75` are fixed in the route; they
  are not tuned per dataset.
- The grey module is excluded from the eigengene table.
- No batch, sex or age covariates are available in this ExpressionSet; the
  module-trait table is unadjusted Pearson correlation only.
