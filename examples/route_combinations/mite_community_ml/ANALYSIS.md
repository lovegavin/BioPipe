# Mite community: diversity, ordination, and shrub-cover classification

## 数据来源

本示例使用 R 包 `vegan` 的公开数据集 `mite` 与 `mite.env`（泥炭沼泽甲螨群落）。数据描述 70 个采样点的 35 个甲螨类群丰度，以及采样点的环境变量。

- 原始数据：R package `vegan`，`data(mite)` / `data(mite.env)`，CRAN: <https://cran.r-project.org/package=vegan>。
- 生态学来源：Borcard, D., Legendre, P., & Drapeau, P. (1992). Partialling out the spatial component of ecological variation. *Ecology*, 73(3), 1045–1055. <https://doi.org/10.2307/1940179>。
- 本示例把 `mite` 的 70×35 丰度矩阵导出为 `input/mite_otu.csv`，把 `mite.env` 的 `Shrub`、`Substrate`、`Topo`、`WatrCont`、`SubsDens` 导出为 `input/mite_meta.csv`；仅数值环境变量 `WatrCont`、`SubsDens` 另存为 `input/mite_env.csv`，供 `envfit` 使用。
- 样本 ID 重新编号为 `M01...M70`；物种列名只做字符清理，不改变类群含义。

### 标签映射

`mite.env` 的 `Shrub` 原始取值为 `None`、`Few`、`Many`。BioPipe 的 CSV Reader 会把字符串 `None` 识别为缺失值，因此示例将 `None` 显式映射为 `NoShrub`，得到三个可比较的类别：

- `NoShrub`：19 个样本；
- `Few`：26 个样本；
- `Many`：25 个样本。

这不是对原始数据的重新编码，只是为了避免 `None` 与缺失值冲突；`ANALYSIS.md` 和图中均使用映射后的名称。

## 数据概况

- 丰度矩阵：70 个样本 × 35 个甲螨类群，非负整数计数。
- 环境表：70 个样本；`Shrub` 为三分类，`Substrate`/`Topo` 为分类变量，`WatrCont`/`SubsDens` 为连续变量。
- 没有缺失样本；`filter_min` 保留全部 35 个类群（至少在 3 个样本中达到 2 个计数）。
- 这是一个小样本、观察性生态数据集，不能据此推断因果，也不构成临床结论。

## 分析路线

任务把“微生物/群落多样性”路线和“机器学习分类”路线展开为扁平 DAG：

1. `filter_min`：按类群过滤低信号，保留至少在 3 个样本中计数 ≥2 的类群；本数据保留 35/35。
2. `diversity`：计算 Shannon、Simpson、richness、evenness 四个 alpha 多样性指标。
3. `distance_matrix`：以 Bray-Curtis 距离描述样本间群落差异。
4. `reduce`：对距离矩阵做 PCoA，保留 5 个成分；PCo1 解释 35.1%，PCo2 解释 11.5%。
5. `permanova`：检验 `Shrub` 三组群落结构差异，999 次置换，随机种子 7。
6. `envfit`：把 `WatrCont`、`SubsDens` 拟合到 PCoA 坐标，报告 R² 与单位长度方向向量；不做置换检验，因此不报告 p 值。
7. `scatter`：绘制 PCoA 的 PCo1–PCo2 散点图。
8. `heatmap`：按方差选前 20 个类群，按样本标准化后聚类展示。
9. `random_forest_classifier`：用 35 个类群丰度预测 `Shrub` 三分类；25% 测试集、3 折交叉验证、200 棵树、标准化。
10. `describe`：输出 PCoA、PERMANOVA、envfit、随机森林结果的摘要。

## 结果

- PCoA：PCo1 35.13%，PCo2 11.55%；前两个轴解释 46.68%。
- PERMANOVA：F = 9.0365，R² = 0.2124，P = 0.001（999 次置换，最小可报告值）。
- envfit：`WatrCont` R² = 0.6664，`SubsDens` R² = 0.2480；单位向量在 PCo1/PCo2 上分别为：
  - `WatrCont`：0.7042 / 0.0169；
  - `SubsDens`：0.0669 / 0.6681。
- 随机森林（测试集 18 个样本）：
  - accuracy 0.6111；
  - macro precision 0.6352；
  - macro recall 0.6048；
  - macro F1 0.6124；
  - AUC 0.7410（三分类 one-vs-rest 平均）；
  - 3 折 CV accuracy 0.6351 ± 0.0169；
  - 混淆矩阵（行/列顺序 `Few`, `Many`, `NoShrub`）：`[[5,2,0],[2,3,1],[2,0,3]]`。
- 随机森林最重要的类群：`MEGR` 0.0821、`TVEL` 0.0806、`ONOV` 0.0742、`HMIN2` 0.0680、`LCIL` 0.0603。

这些结果表明灌木覆盖与甲螨群落结构有可检测的关联，但三分类预测只有中等水平；35 个类群、70 个样本不足以支持强预测结论。

## 图

- `output/figures/pcoa.png`：PCoA 的 PCo1–PCo2 散点图。图上没有着色分组，因为当前 `join` 输出会丢失 component 标签，`scatter` 无法安全接收带元数据的坐标；分组差异由 PERMANOVA 定量给出。若只做无着色散点，当前路线保持类型契约完整。
- `output/figures/top20_species_heatmap.png`：前 20 个高方差类群、按样本标准化、行/列聚类。

## 假设与限制

- `mite` 是丰度计数；本示例没有做 rarefaction，也没有做组成性数据转换。`diversity` 直接使用计数，`distance_matrix` 使用 Bray-Curtis。
- `filter_min` 的阈值是示例选择，不来自原始论文；本数据没有删除类群。
- PERMANOVA 的 P = 0.001 是 999 次置换下的分辨率下限，不能解释为精确的 0.001。
- `envfit` 只报告线性向量拟合，不做置换 p 值；R² 是拟合优度，不是因果效应。
- 随机森林的测试集只有 18 个样本，AUC 与 accuracy 的不确定性很大；CV 采用 3 折，类别分层由算子内部处理。
- `Shrub` 的 `None → NoShrub` 映射是读取层适配，不是生物学分组变化。
- 该数据是生态学观察数据，结论仅限于本示例的演示目的。

## 复现

在项目根目录执行：

    python scripts/run.py examples/route_combinations/mite_community_ml

只做静态校验：

    python scripts/run.py examples/route_combinations/mite_community_ml --check

输出写入 `examples/route_combinations/mite_community_ml/output/`；`output/` 已被 `.gitignore` 忽略。
