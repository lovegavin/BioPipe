# 16S microbiome route

The `16S Microbiome` template adapts the COMPASS-DOE abundance-table workflow from
upstream commit `fa267bc46a30ee9c9483b7442ff119b9aefcf62c`. It contains two input
ports, 22 processing/report steps, nine exposed data outputs and five figures.
The source template is `routes/microbiome/task.yaml`.

This is downstream OTU/ASV abundance analysis. FASTQ QC, denoising, chimera removal,
taxonomic assignment, rarefaction and phylogenetic UniFrac are not implemented by
this route. Its original input filename refers to a table already rarefied to
20,000 reads. BioPipe does not perform that rarefaction implicitly.

## Inputs and branches

| Input | Layout | Required fields |
| --- | --- | --- |
| OTU abundance CSV | `[species, sample]`; first column contains species IDs | Numeric, nonnegative abundances; sample IDs in the header |
| Sample metadata CSV | `[sample, feature]`; first column contains sample IDs | `site`, `horizon`, `transect` |

The existing CSV Reader encodes categorical metadata and preserves column
encoders. Sample IDs align the tables. Route input nodes are placeholders; connect
your own uploaded/read data or open the route graph and set input paths. Replace
the example grouping columns and thresholds for your study before running.

The default filter retains species with values at least 10 in at least five
samples. From the filtered sample-by-species matrix the route branches into:

- Total normalization and alpha diversity: Shannon, Simpson, richness, evenness.
- Bray-Curtis/Jaccard distances, Bray-Curtis PCoA, metadata join, three scatter plots.
- PERMANOVA for site, horizon and transect (999 permutations; fixed random seed 0).
- Sample Spearman correlation and a clustered heatmap.
- Group means by site and a normalized stacked composition barplot.

PCoA retains up to five positive-eigenvalue components; the demo scatters request
PCo1 and PCo2. Very small or degenerate inputs may not have two positive components
and require adjusting the plot parameters. A PERMANOVA comparison also needs
adequate samples and multiple valid groups. Statistical suitability remains a
property of the study design; automatic registration does not establish it.

## Provider and capabilities

`biopipe-microbiome` contains eight independently addressable operators:

| ID | Output | Main options |
| --- | --- | --- |
| `diversity` | Surviving dimensions plus `metric` | Shannon, Simpson, richness, evenness, Gini |
| `distance_matrix` | `[dim, dim_b]` | Euclidean, Manhattan, cosine, correlation, Bray-Curtis, Jaccard, Hamming |
| `reduce` | Observations by `component` | PCA, PCoA; optional UMAP/t-SNE |
| `join` | Aligned data plus metadata columns | Inner/left, column selection, prefix |
| `permanova` | `comparison` by `statistic` | Overall/pairwise tests, permutations, seed |
| `correlation` | `[dim, dim_b]` | Pearson, Spearman, Kendall, cosine, Jaccard, overlap |
| `aggregate` | Groups by retained features | Sum, mean, median, min, max, count |
| `barplot` | Figure and report | Top N, Other category, normalization, legend/style |

All eight expose JSON Schema parameters and executable contracts. Changed axes
drop obsolete annotations; surviving annotations remain aligned. Joined row
annotations follow the matched sample order, and newly appended columns receive
null feature annotations. Derived values clear obsolete genotype semantics.
Duplicate or differently ordered distance labels are rejected where order matters.

The eight kernels are CPU, full-memory implementations. Their estimates include
float64 workspaces, outputs and label storage. Pairwise matrices scale as N²;
PCoA also reserves dense eigensolver space. The fixed startup budget, admission
checks, cache reuse and emergency spill continue to govern execution. Spill can
release evictable cached forms, but cannot interrupt an in-progress NumPy/SciPy
allocation. An admitted estimate is not a hard native-memory ceiling.

`distance_matrix` and `correlation` accept an optional `max_positions` guard.
The adapter defaults it to null, using budget-based admission instead of the
upstream fixed 10,000-position cap. Explicit positive limits are still honored.
The shipped 16S template enables memory management. Standalone legacy YAML only
uses admission checks when `runtime.memory.enabled` is true.

The Reader package keeps H5AD/MTX `dense-writer-v1` preparation, and `describe`
keeps `flat-reduction-v1` streaming. Registering these new operators does not
remove either capability and does not turn the new kernels into stream operators.

The shipped 16S methods use the base NumPy/SciPy/Matplotlib dependencies. Only
`reduce(method=umap)` needs `umap-learn`; `reduce(method=tsne)` needs
`scikit-learn`. Install those in the backend environment if selecting those methods.

## Maintenance and tests

```bash
python -m biopipe registry build
python -m biopipe registry check
python -m pytest -q tests/test_microbiome.py tests/test_builtin_routes.py tests/test_registry_maintenance.py
python scripts/build_builtin_packages.py --package biopipe-microbiome --output .tmp/packages
```

The workflow tests run synthetic input through all 22 steps and check five figures;
they do not claim replication of the original research dataset. Numerical tests
cover diversity, distance/correlation, PCoA, metadata joins and aggregation.
Resource tests check quadratic admission and preserve existing disk/stream tests.
See [registry maintenance](registry_maintenance.md) for adding more routes without
changing generator code. This source update does not rebuild or synchronize the
desktop distribution.
