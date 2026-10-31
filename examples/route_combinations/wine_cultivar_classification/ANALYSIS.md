# UCI Wine 品种分类：线性判别、随机森林与特征结构

## 数据来源

- 数据集：UCI Machine Learning Repository, Wine Data Set，178 个样本、13 个连续化学特征、3 个品种（cultivar）。
- 类别分布：cultivar_1 = 59、cultivar_2 = 71、cultivar_3 = 48；无缺失值。
- 本示例通过 scikit-learn 的 load_wine 读取同一公开数据的打包副本，样本 ID 重新编号为 wine_001...wine_178。
- 原始提供者：Forina, M. et al., PARVUS - An Extendible Package for Data Exploration, Classification and Correlation；数据页面：https://archive.ics.uci.edu/dataset/109/wine；scikit-learn 页面：https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html。
- 本示例只做方法演示，不构成品种鉴定、质量控制或临床结论。

## 输入与整理

- **input/wine_features.csv**：sample + 13 个特征（alcohol、malic_acid、ash、alcalinity_of_ash、magnesium、total_phenols、flavanoids、nonflavanoid_phenols、proanthocyanins、color_intensity、hue、od280/od315_of_diluted_wines、proline）。
- **input/wine_labels.csv**：sample、class（0/1/2）与 class_label（cultivar_1/2/3）。分类模型使用字符串 class_label，避免把类别编码误当成有序数值。
- 不删除样本、不插补、不做手工标准化。LDA 在 pipeline 内标准化；随机森林使用原始特征尺度。
- 固定 random_state=11、test_size=0.25、cv_folds=5；LDA 与随机森林使用同一划分，便于比较。

## 路线组合（9 步）

1. **lda_classifier**：13 个特征 + 3 类标签，线性判别分析；输出特征判别权重与分类指标。
2. **describe**：汇总 LDA 权重表。
3. **random_forest_classifier**：500 棵树，同一特征/标签与划分；输出特征重要性与分类指标。
4. **describe**：汇总随机森林重要性表。
5. **pca**：对 13 个特征做 2 成分 PCA，观察无监督结构。
6. **join**：把 class_label 并到 PCA 坐标。
7. **scatter**：按品种着色绘制 PC1–PC2。
8. **correlation**：13×13 Pearson 相关矩阵。
9. **heatmap**：聚类行/列的相关热图。

前四个步骤比较线性判别与非线性集成的分类表现；后五个步骤检查无监督结构与特征间冗余。整条任务只使用已有算子与 Reader，registry 不变。

## 分类结果

### LDA

- 训练 133、测试 45；测试集类别数 15/18/12。
- 测试 accuracy **1.0000**、macro precision **1.0000**、macro recall **1.0000**、macro F1 **1.0000**、macro OVR AUC **1.0000**。
- 混淆矩阵：[[15, 0, 0], [0, 18, 0], [0, 0, 12]]，测试集无错分。
- 5 折 CV accuracy：[1.0000, 0.9630, 0.9630, 1.0000, 1.0000]，均值 **0.9852**，标准差 **0.0181**。
- 权重最大的特征：flavanoids **0.5927**、color_intensity **0.4966**、malic_acid **0.2015**、hue **0.1612**、od280/od315 **0.1282**。多分类 LDA 的 signed_score 是各类系数的均值，只用于排序/方向参考，不能当作单变量因果效应。

### 随机森林

- 测试 accuracy **0.9556**、macro precision **0.9667**、macro recall **0.9556**、macro F1 **0.9586**、macro OVR AUC **1.0000**。
- 混淆矩阵：[[13, 2, 0], [0, 18, 0], [0, 0, 12]]；2 个 cultivar_1 被分为 cultivar_2，其余正确。
- 5 折 CV accuracy：[1.0000, 0.9630, 1.0000, 0.9615, 0.9615]，均值 **0.9772**，标准差 **0.0186**。
- 重要性最高的特征：color_intensity **0.1669**、proline **0.1623**、flavanoids **0.1514**、alcohol **0.1133**、od280/od315 **0.1069**。

### 解释边界

- LDA 在 45 个测试样本上全对，但测试集很小，且 Wine 是类别分离度较高的经典数据集；**不能据此声称模型可泛化到新产区或新品种**。5 折 CV 的 0.985 也只能说明这份数据内部稳定。
- 随机森林没有超过 LDA，说明这份数据的主要判别信息近似线性；树模型的额外非线性没有带来测试集收益，且多错了 2 个样本。
- 两个模型的重要特征都集中在 flavanoids、color_intensity、proline、alcohol、od280/od315 附近，方向一致，说明结果不是某一个模型独有的伪影。
- AUC 为 1.0 而随机森林 accuracy 为 0.9556 并不矛盾：AUC 衡量概率排序，随机森林仍可能把个别样本分到错误类别；不要只看 AUC。

## 无监督结构与相关性

- PCA：PC1 解释 **36.20%**，PC2 解释 **19.21%**，前两轴合计 **55.41%**。
- 类别在 PC1–PC2 上呈明显分离：cultivar_1 偏左、cultivar_3 偏右、cultivar_2 偏上；这与 LDA 的高准确率一致。PCA 不使用标签，分离不是标签泄漏造成的。
- Pearson 相关范围 **-0.5613 到 0.8646**。最高正相关：total_phenols–flavanoids **0.8646**、flavanoids–od280/od315 **0.7872**、total_phenols–od280/od315 **0.6999**、flavanoids–proanthocyanins **0.6527**、alcohol–proline **0.6437**；最强负相关：malic_acid–hue **-0.5613**。
- 这些相关说明特征之间存在明显的化学/测量共变，后续建模若要解释单个特征，需考虑共线性；随机森林重要性也会把相关特征的信息分散到多个变量上。

## 限制

- 数据只有 178 行、3 个品种，测试集 45 行；单次划分的 accuracy 方差很大，本示例用 5 折 CV 作为补充，但仍不是外部验证。
- 没有独立批次、产区、年份或测量平台信息，无法评估批次效应与跨域泛化。
- 相关矩阵是描述性的，不能推断因果；特征名称与化学含义来自原数据集，未做额外实验验证。
- LDA 的完美测试是这份数据的特性，不应作为方法优越性的证据；随机森林与 LDA 的差异也只有 2 个测试样本。

## 复现

在项目根目录执行：

    python scripts/run.py examples/route_combinations/wine_cultivar_classification --check
    python scripts/run.py examples/route_combinations/wine_cultivar_classification

输出在 **output/**：**figures/pca_by_cultivar.png**、**figures/chemical_correlation.png**，以及每步 JSON 与运行摘要。output/ 不提交；重新运行即可再生。
