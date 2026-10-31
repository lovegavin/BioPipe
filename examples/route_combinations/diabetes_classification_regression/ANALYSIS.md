# Diabetes: 分类 + 回归 + PCA 路线组合

## 目的

本示例把两条内置路线展开到同一个公开数据任务中：

- **机器学习分类**：用 10 个基线特征预测“疾病进展是否高于中位数”；
- **机器学习回归**：用同一组特征预测连续进展值；
- 额外用 **PCA + 散点图** 观察高/低进展组在无监督空间中的重叠程度。

任务不新增算子、Reader 或内置路线，只组合已有的 `random_forest_classifier`、`ridge_regression`、`pca`、`join`、`scatter` 与 `describe`。

## 数据来源

- 数据集：scikit-learn `sklearn.datasets.load_diabetes`，442 个样本、10 个数值特征，目标为基线后一年的疾病进展指标。
- 特征：`age, sex, bmi, bp, s1, s2, s3, s4, s5, s6`。scikit-learn 提供的是已经中心化/缩放后的版本，适合方法演示，不等于原始临床测量尺度。
- 分组：按目标中位数 **140.0** 生成 `high_progression`（`high` 223 例、`low` 219 例）。该标签由目标值派生，仅用于演示分类路线，不是独立临床诊断标签。
- 引用：Efron, B., Hastie, T., Johnstone, I., & Tibshirani, R. (2004). Least Angle Regression. *Annals of Statistics*, 32(2), 407–499. 数据说明亦见 scikit-learn 的 `load_diabetes` 文档：<https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_diabetes.html>。

## 任务结构

输入：

- `input/diabetes_features.csv`：`sample` + 10 个特征；
- `input/diabetes_labels.csv`：`sample, progression, high_progression`。

分支：

1. `random_forest_classifier`：目标 `high_progression`，300 棵树，25% 测试集，3 折交叉验证，`random_state=17`；
2. `ridge_regression`：目标 `progression`，`alpha=1.0`，同样 25% 测试集与 3 折交叉验证；
3. `pca`：对 10 个特征取前 2 个主成分；
4. `join`：把 `high_progression` 贴到 PCA 坐标；
5. `scatter`：PC1–PC2 散点，按高/低进展组着色；
6. 两个 `describe` 分别摘要分类与回归的导出指标。

## 结果

### 分类（随机森林）

- 测试集：111 例；训练集：331 例。
- Accuracy **0.7297**；macro precision **0.7300**；macro recall **0.7295**；macro F1 **0.7295**；AUC **0.8430**。
- 3 折 CV accuracy **0.7220 ± 0.0354**。
- 混淆矩阵（行/列顺序为 `high, low`）：`[[42, 14], [16, 39]]`。
- 重要性最高的特征：`s5` 0.1941、`bmi` 0.1874、`bp` 0.1238、`s2` 0.0951、`s3` 0.0926。

### 回归（Ridge）

- 测试 RMSE **53.515**；MAE **42.713**；测试 R² **0.4877**。
- 3 折 CV R² **0.4780 ± 0.0914**。
- 系数绝对值最大的特征：`s5` 27.59、`bmi` 23.59、`sex` −15.60、`bp` 14.71。

### PCA

- PC1 解释 **40.24%**，PC2 解释 **14.92%**；前两轴合计 55.17%。
- 散点图：`output/figures/pca_by_progression_group.png`，442 个点，按 `high/low` 着色。两组在 PC1–PC2 上明显重叠，说明这 10 个特征不能把进展组完全分开；分类指标应结合这一无监督视图解读。

## 解释与限制

- 分类标签由连续目标的中位数派生，因此分类与回归不是两个独立问题；AUC/accuracy 只说明该派生标签的可分性。
- 特征已由 scikit-learn 标准化；示例没有重新拟合标准化器，也没有做外部验证。
- 随机森林与 Ridge 使用相同特征、相同划分比例，但两者的测试集划分由各自模型内部完成；不要逐样本比较两个模型的残差。
- 示例用于展示路线组合与可复现任务结构，不构成临床预测结论。
- 没有新增算子或 Reader；如果后续需要概率校准、决策曲线或外部验证，应优先复用已有算子并另写批次。

## 复现

    python scripts/run.py examples/route_combinations/diabetes_classification_regression --check
    python scripts/run.py examples/route_combinations/diabetes_classification_regression

输出在 `output/`：`run_summary.txt/json`、`steps/*.json` 和 `figures/pca_by_progression_group.png`。
