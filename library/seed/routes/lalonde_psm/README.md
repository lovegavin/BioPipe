# Lalonde propensity-score matching and balance

Estimate the average treatment effect on the treated (ATT) of a job-training
programme with propensity-score nearest-neighbour matching, then report
covariate balance before and after matching.

## Data

`MatchIt::lalonde` (R package MatchIt 4.8.2), the classic Lalonde (1986)
experimental subsample: 614 observations, 185 treated, 429 control, 8
covariates (`age`, `educ`, `black`, `hispan`, `married`, `nodegree`, `re74`,
`re75`). Outcome is `re78` (1978 earnings). `race` is expanded into the two
0/1 indicators used by the standard specification.

- `input/lalonde.csv`, sha256
  `274e610279fe5e5b57a50073b0124af9d602beb1a07cb3da4f09a7acb3393602`
  (614 rows, 10 columns).

## Route

| # | operator | purpose |
|---|----------|---------|
| 1 | `propensity_score` | logistic propensity model (IRLS, 8 covariates) |
| 2 | `psm_match` | nearest neighbour, caliper 0.2 SD, ratio 1, largest first |
| 3 | `psm_balance` | SMD and variance ratio before/after matching |
| 4 | `psm_effect` | ATT, standard error, t, p, 95% CI on matched pairs |
| 5-8 | `export_results` | CSV exports for all four tables |

Total runtime is 0.016 s on the reference machine.

## Results

- Propensity model: AUC **0.874227**, 7 IRLS iterations, scores in
  [0.00908, 0.85315]; treated 185, control 429.
- Matching: **113 pairs** (226 units), 72 treated unmatched, caliper
  **0.058063** (0.2 x SD of the propensity score, SD 0.290313).
- Balance: max |SMD| falls from **1.667719** (`black`) to **0.148668**
  (`nodegree`); all eight covariates are below 0.15 after matching.
- Effect: ATT **1571.744454**, SE 981.867698, t 1.600770, p 0.109428,
  95% CI [-352.680870, 3496.169779].

## Oracles

R `MatchIt` 4.8.2 (`matchit(treat ~ 1, distance = ps, method = "nearest",
caliper = 0.2, std.caliper = TRUE, ratio = 1, replace = FALSE)`), with
independent GLM coefficients from `glm()` and SMDs recomputed in base R.

| quantity | Operon | R oracle | difference |
|---|---|---|---|
| matched pairs | 113 | 113 | 0 |
| propensity score | - | `predict(glm)` | max abs 3.14e-9 |
| logit score | - | - | max abs 5.55e-16 |
| ATT | 1571.7444544 | 1571.7444544 | 9.09e-13 |
| SMD before (8 covariates) | - | - | max abs 1.67e-16 |
| SMD after (8 covariates) | - | - | max abs 6.94e-17 |
| max abs SMD after | 0.1486684550 | 0.1486684550 | 0 |
| caliper (absolute) | 0.0580626745 | 0.0580626745 | 0 |

## Assumptions and limits

- The caliper is expressed in standard deviations of the propensity score
  (`0.2 * sd(score)`), matching `MatchIt` with `std.caliper = TRUE` on the
  propensity scale.
- Matching is 1:1 without replacement and greedy in descending score order;
  ties are resolved by row order.
- The standard error is the OLS residual standard error on the matched sample
  and does not implement the Abadie-Imbens variance estimator.
- SMD uses the pooled standard deviation with `ddof = 1`; variance ratios are
  reported alongside but not used for matching decisions.
- Only the ATT is estimated; control-side effects require a different route.
