# UCI 乳腺癌：差异分析 + 随机森林分类

## 数据

- 特征表：`input/breast_cancer_features.csv`，569 个样本 × 30 个数值特征。
- 标签表：`input/breast_cancer_labels.csv`，`diagnosis` 为 `benign`（357）或 `malignant`（212）。
- 来源：UCI Machine Learning Repository, Breast Cancer Wisconsin (Diagnostic) Data Set；通过 scikit-learn `load_breast_cancer` 读取同一公开数据。样本 ID 已重新编号为 `BC0001...`，特征名整理为 `mean_radius`、`worst_concave_points` 等。
- 引用：Street, W.N., Wolberg, W.H., Mangasarian, O.L. (1993). Nuclear feature extraction for breast tumor diagnosis. *IS&T/SPIE 1993 International Symposium on Electronic Imaging*.
- 原始页面：<https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic>

数据无缺失值。特征是细胞核图像的形态测量汇总（均值、标准误、最差值），不是原始像素。

## 分析步骤

1. **compare_groups（Welch t 检验）**：按 `diagnosis` 比较良性（group_a，n=357）与恶性（group_b，n=212）的 30 个特征。输出 `log2FC`、两组均值、t 统计量和 P 值。`log2FC` 为正表示该特征在恶性组更高。
2. **volcano**：以 `log2FC` 为横轴、`-log10(P)` 为纵轴，阈值 `|log2FC| > 1`、`P < 0.05`；图中最多展示 20 个特征，因此计数是“展示子集”的计数，不是全部 30 个特征。
3. **ma_plot**：以两组均值为横轴、`log2FC` 为纵轴，检查差异是否依赖丰度；图中同样最多展示 20 个特征。
4. **heatmap**：按方差选前 30 个特征，按行标准化后做层次聚类，展示样本间整体模式。
5. **random_forest_classifier**：用 30 个特征做良恶性二分类；75% 训练、25% 测试，3 折交叉验证，`random_state=7`，200 棵树。
6. **describe**：汇总随机森林输出的特征重要性表。

## 主要结果

- 30 个特征全部完成 Welch 检验；多数形态特征在恶性组更高。例如 `mean_radius`：良性均值 12.15、恶性均值 17.46，`log2FC=0.506`，`P=1.68e-64`。
- 火山图展示的 20 个特征中：**1 个上调、0 个下调、19 个不显著**（按 `|log2FC|>1` 与 `P<0.05`）。这说明该数据的统计显著性很强，但达到 2 倍差异阈值的特征很少；MA 图展示的 20 个特征中有 16 个显著。
- 随机森林：训练 426、测试 143；测试准确率 **0.930**，宏平均精确率 **0.937**，宏平均召回率 **0.913**，宏平均 F1 **0.923**，AUC **0.971**；3 折 CV 准确率 **0.958 ± 0.011**。
- 混淆矩阵（行=真实 benign/malignant，列=预测）：`[[88, 2], [8, 45]]`。
- 重要性最高的特征：`worst_radius`（0.140）、`worst_perimeter`（0.117）、`mean_concave_points`（0.113）、`worst_concave_points`（0.112）、`worst_area`（0.099）。

## 图

- `output/figures/volcano.png`：恶性相对良性的差异；正 `log2FC` 为恶性组更高。
- `output/figures/ma.png`：两组均值与差异幅度；用于判断差异是否集中在低丰度特征。
- `output/figures/top30_heatmap.png`：前 30 个高方差特征、行标准化后的样本聚类。

## 假设与限制

- 这是公开的诊断数据集，特征是已经提取好的细胞核测量，不是原始图像；不能把结果直接外推到其他医院、扫描仪或人群。
- 随机划分的训练/测试集共享同一数据分布；高准确率主要反映该数据集的强可分性，不等于外部验证性能。
- 火山图和 MA 图默认最多展示 20 个特征；文字中的“上调/下调”计数只针对图中展示的子集。
- 本示例用于演示路线组合和结果可追溯性，不构成临床诊断建议。
