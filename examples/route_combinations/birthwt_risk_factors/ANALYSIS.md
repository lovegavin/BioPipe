# MASS birthwt：低出生体重风险因素的路线分析

## 数据来源与处理

- 数据集：R 包 MASS 的 `birthwt`，189 例单胎出生记录，来自 Baystate Medical Center（Springfield, MA）的低出生体重研究。
- 经典引用：Hosmer, D. W. & Lemeshow, S. (2000). *Applied Logistic Regression*, 2nd ed. Wiley；R 包来源 Venables, W. N. & Ripley, B. D. (2002). *Modern Applied Statistics with S*, 4th ed. Springer。
- 原始变量：`low`（出生体重 < 2500 g）、`age`（母亲年龄）、`lwt`（末次月经体重，磅）、`race`（1/2/3）、`smoke`、`ptl`（早产史次数）、`ht`（高血压）、`ui`（子宫应激）、`ftv`（产前就诊次数）、`bwt`（出生体重，克）。
- 本分析只使用基线风险因素，不使用 `bwt` 作为预测变量，避免把结局泄漏进特征。
- 189 例完整，无缺失；低出生体重 59 例（31.2%），正常 130 例（68.8%）。
- `race` 是社会经济/群体变量，不是生物学变量；为便于数值模型，按 race=1 为参照构造 `race_2`、`race_3` 两个 0/1 指示变量。解释时不能把 race 系数当作因果效应。
- 生成方式：直接从 R 的 `MASS::birthwt` 导出，未手工改数值；只增加了样本 ID 和 `low_label` 文本标签。

## 路线

```text
birthwt_features.csv ─┬─ compare_groups ─ describe
birthwt_labels.csv  ──┘
                      ├─ logistic_regression ─ describe
                      ├─ random_forest_classifier ─ describe
                      ├─ pca ─ join(labels) ─ scatter
                      └─ correlation(Spearman) ─ heatmap
```

分支含义：

1. `compare_groups`：按 `low_label` 比较正常/低出生体重两组母亲年龄与体重，Welch t 检验。
2. `logistic_regression`：9 个基线特征预测 `low`，不做标准化，使用很弱的 L2 正则（C=1e6）以接近未惩罚 MLE；输出系数方向和近似 OR。
3. `random_forest_classifier`：同一组特征做非线性分类，报告测试集和 3 折交叉验证。
4. `pca`：对 9 个特征做相关矩阵 PCA，取前两主成分；`join` 标签后用 `scatter` 着色。
5. `correlation` + `heatmap`：Spearman 相关矩阵，检查风险因素之间的共线性。

## 结果

### 1. 两组母亲基线比较

| 指标 | 正常组均值 (n=130) | 低出生体重组均值 (n=59) | Welch t | P |
|---|---:|---:|---:|---:|
| 母亲年龄（岁） | 23.662 | 22.305 | -1.774 | 0.0783 |
| 末次月经体重（磅） | 133.300 | 122.136 | -2.516 | 0.0131 |

低出生体重组母亲的平均体重低约 11.2 磅，差异有统计学意义；年龄差异约 1.36 岁，证据较弱。这是描述性比较，不能单独解释为因果。

### 2. 逻辑回归

测试集 48 例，训练集 141 例；测试准确率 0.688，AUC 0.667；3 折 CV 准确率 0.681 ± 0.052。

| 特征 | 系数 | 近似 OR | 解释 |
|---|---:|---:|---|
| `ht`（高血压） | 2.100 | 8.17 | 高血压与低出生体重风险正相关 |
| `race_3`（race=3 vs 1） | 1.282 | 3.60 | 群体差异，非生物学效应 |
| `race_2`（race=2 vs 1） | 1.019 | 2.77 | 群体差异，非生物学效应 |
| `smoke`（吸烟） | 0.846 | 2.33 | 吸烟与更高风险相关 |
| `ptl`（早产史次数） | 0.644 | 1.90 | 每增加一次早产史，风险更高 |
| `ui`（子宫应激） | 0.043 | 1.04 | 方向为正但效应很小 |
| `age`（每岁） | -0.048 | 0.953 | 调整后方向为负，证据弱 |
| `ftv`（每次产前就诊） | -0.039 | 0.962 | 方向为负，效应很小 |
| `lwt`（每磅） | -0.019 | 0.981 | 每增加 10 磅，近似 OR 0.829 |

注意：`logistic_regression` 只输出系数/重要性，不输出标准误、P 值或 OR 置信区间；这里的 OR 是系数指数化后的描述值，不是带推断的效应量。C=1e6 使 L2 惩罚很弱，但仍不是完全无惩罚的统计推断。

### 3. 随机森林

测试集准确率 0.729，AUC 0.815；3 折 CV 准确率 0.610 ± 0.010。混淆矩阵（行=真实 low/normal，列=预测 low/normal）：

```text
[[ 5, 10],
 [ 3, 30]]
```

即低出生体重组 15 例中只识别出 5 例（召回率 33%），正常组 33 例中识别出 30 例。AUC 尚可但默认阈值下对少数类不敏感，不能只看准确率。特征重要性前五：`lwt` 0.334、`age` 0.275、`ftv` 0.107、`ptl` 0.077、`smoke` 0.050。

### 4. PCA

PC1 解释 19.24%，PC2 解释 15.74%，前两轴合计 34.98%。低/正常组在 PC1-PC2 平面上明显重叠，说明这 9 个基线风险因素没有形成强的低维分组结构；PCA 主要作为无监督检查，而不是分类证据。

![PCA by birthweight group](output/figures/pca_by_birthweight_group.png)

### 5. 风险因素相关性

9×9 Spearman 相关矩阵的系数范围为 -0.323 到 0.234，最大绝对相关约 0.323；没有特别强的两两共线性。热图用于检查相关结构，不替代多变量模型。

![Risk factor Spearman correlation](output/figures/risk_factor_correlation.png)

## 解释与限制

- 这是观察性关联分析，不是因果分析；高血压、吸烟、早产史等不能直接解释为干预效应。
- `race` 系数反映的是数据中的群体差异，受社会经济、医疗可及性等未测混杂影响，不应作生物学解释。
- 逻辑回归没有输出推断标准误/P 值/OR CI；OR 仅作方向性描述。若需要严格推断，应使用带完整协方差输出的回归算子或外部 R/Python 模型。
- 测试集只有 48 例，AUC/准确率波动大；随机森林的 CV 准确率低于逻辑回归，且对低出生体重类召回率低。
- 数据是 1986 年的历史单中心样本，不能直接外推到当代或其他人群。
- 本分析没有新增算子或 Reader；全部由现有 route 组合完成。

## 复现

```bash
python scripts/run.py examples/route_combinations/birthwt_risk_factors --check
python scripts/run.py examples/route_combinations/birthwt_risk_factors
```

输出在 `output/`：`run_summary.txt`、逐步 JSON、`figures/pca_by_birthweight_group.png`、`figures/risk_factor_correlation.png`。
