# B9 model selection route

Breast Cancer Wisconsin (sklearn 1.6.1 public dataset, 569 samples x 30 features;
357 benign / 212 malignant). Split/fold assignment is reproduced bit-for-bit from
scikit-learn's stratified samplers.

## Steps

1. `ml_stratified_folds` - 5-fold stratified assignment (seed 0)
2. `ml_train_test_split` - stratified 75/25 split (426 train / 143 test)
3. `ml_logistic_fit` - standardized L2 logistic regression (C=0.01)
4. `ml_feature_ablation` - refit without each feature, log-loss delta

## Results

- folds: 5, sizes 114/114/114/114/113
- logistic: accuracy 0.956063, ROC AUC 0.994160, n_iter 16
- ablation top-3: worst texture, worst concave points, worst radius

## Oracle (scikit-learn 1.6.1)

| item | result |
| --- | --- |
| StratifiedKFold vs operator | identical, 0 mismatches |
| StratifiedShuffleSplit vs operator | identical, 426/143 |
| LogisticRegression coef / intercept | max abs diff 9.45e-09 / 2.29e-09 |
| predicted probability | max abs diff 2.90e-08 |
| per-feature log-loss delta | max abs diff 3.34e-09, top-3 identical |

## Limitations

- Coefficients are only comparable after standardization (features are collinear;
  unstandardized coefficients are not identifiable but probabilities agree).
- Ablation uses refit cost; it is not a causal importance measure.
