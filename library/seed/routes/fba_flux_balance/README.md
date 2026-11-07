# Metabolic flux balance analysis

Flux balance analysis (FBA) of the BiGG *E. coli* core model, together with a
single-gene knockout scan and a flux variability analysis. The model is the
published small-scale reconstruction, so the route runs in seconds on a laptop.

## Data

| File | Size | SHA256 |
| --- | --- | --- |
| `input/e_coli_core.xml` | 707,166 B | `b4db506aeed0e434c1f5f1fdd35feda0dfe5d82badcfda0e9d1342335ab31116` |

Model contents: 95 reactions, 72 metabolites, 137 genes. Source:
<http://bigg.ucsd.edu/models/e_coli_core> (BiGG Models).

## Steps

| Step | Operator | Output |
| --- | --- | --- |
| 1 | `fba_flux_distribution` | flux, fraction of maximum, active flag per reaction |
| 2 | `export_results` | `fba_flux_distribution.csv` |
| 3 | `fba_gene_knockout` | growth rate, growth ratio and essential flag per gene |
| 4 | `export_results` | `fba_gene_knockout.csv` |
| 5 | `fba_flux_variability` | minimum and maximum flux per reaction at 90% of maximum growth |
| 6 | `export_results` | `fba_flux_variability.csv` |

## Results (WSL, 2026-11-07)

Total elapsed time 0.72 s (fluxes 0.190 s, knockouts 0.228 s, variability 0.297 s).

* Maximum growth rate: **0.8739215069684304 h^-1**.
* Active reactions: 53 of 95; phosphofructokinase (R_PFK) carries
  7.477381962160283 mmol gDW^-1 h^-1 and pyruvate formate lyase (R_PFL) is
  inactive under aerobic conditions.
* Essential genes: **7** (b0720, b1136, b1779, b2415, b2416, b2779, b2926).
* Flux variability at 90% of maximum growth: R_PFK ranges from 1.1717 to
  25.2906 mmol gDW^-1 h^-1, i.e. the optimum is strongly degenerate.

## Oracle comparison

Two independent implementations were used.

| Oracle | Version | Metric | Result |
| --- | --- | --- | --- |
| cobra | 0.32.1 | growth rate | abs 8.9e-16 |
| cobra | 0.32.1 | knockout growth, 137 genes | max abs 4.5e-15 |
| cobra | 0.32.1 | essential gene set | identical, 7 of 7 |
| cobra | 0.32.1 | FVA at 90%, 95 reactions | max abs 1.0e-12 |
| glpsol | GLPK 5.0 | growth rate | abs 3.2e-11 |
| glpsol | GLPK 5.0 | 7 knockout growth rates | max abs 7.8e-13 |
| glpsol | GLPK 5.0 | FVA on 8 reactions | max abs 4.1e-9 |

cobra reports `infeasible` for two deletions (b2415, b2416); those are recorded
as zero growth, which is the biological reading of a lethal knockout.

## Limitations

* The model is the BiGG core reconstruction; it is not a genome-scale model.
* Only the default biomass objective is optimised; no parsimonious FBA and no
  thermodynamic constraints are applied.
* Gene knockouts act through the GPR rules only; no regulatory or expression
  data are considered.
* Flux variability is evaluated at a single fraction (90%) of maximum growth.
* Degenerate optima mean individual flux values are not unique; the variability
  interval, not a single flux vector, is the comparable quantity.
