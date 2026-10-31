# 路线组合示例

本目录把 BioPipe 的多条内置路线组合成可直接运行的分析任务。示例**只使用已有算子与 Reader**，不新增注册项，因此 registry 仍为 402 个算子、85 个 Reader、21 条 route。

## 示例

| 目录 | 组合的路线 | 数据与目的 |
|---|---|---|
| `cancer_diagnosis_ml/` | 差异分析 + 可视化 + 机器学习分类 | UCI 乳腺癌诊断数据；比较良恶性特征差异，并用随机森林做良恶性分类 |
| `lung_regression_survival/` | 回归 + 生存分析 + 可视化 | NCCTG 肺癌数据；用生理指标回归年龄，并做性别分层 KM、log-rank 与 Cox 分析 |
| `mite_community_ml/` | 群落多样性 + 排序/环境拟合 + 机器学习分类 | `vegan::mite` 泥炭沼泽甲螨数据；alpha 多样性、Bray-Curtis PCoA、PERMANOVA/envfit，以及随机森林预测灌木覆盖 |

三个示例都使用公开、可引用的数据集，而不是临时合成数据。数据已放在各自的 `input/` 下，便于离线复现。

## 运行

在项目根目录执行：

    python scripts/run.py examples/route_combinations/cancer_diagnosis_ml
    python scripts/run.py examples/route_combinations/lung_regression_survival
    python scripts/run.py examples/route_combinations/mite_community_ml

只做静态校验：

    python scripts/run.py examples/route_combinations/cancer_diagnosis_ml --check
    python scripts/run.py examples/route_combinations/lung_regression_survival --check
    python scripts/run.py examples/route_combinations/mite_community_ml --check

每个示例的输出写入各自 `output/`：`figures/` 为图片，`steps/` 为每步 JSON 摘要，`run_summary.txt/json` 为运行摘要。`input/` 中的 CSV 来自公开数据集，字段经过最小化整理；示例用于演示组合方式，不构成临床或生物学结论。

## 数据来源

### UCI Breast Cancer Wisconsin (Diagnostic)

- 569 个样本，30 个数值特征；良性 357、恶性 212。
- 原始数据：UCI Machine Learning Repository, Breast Cancer Wisconsin (Diagnostic) Data Set，<https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic>。
- 本示例通过 scikit-learn `sklearn.datasets.load_breast_cancer` 读取同一公开数据，样本 ID 重新编号为 `BC0001...`，特征名整理为 `mean_radius` 等；标签写为 `benign` / `malignant`。
- 引用：Street, W.N., Wolberg, W.H., Mangasarian, O.L. (1993). Nuclear feature extraction for breast tumor diagnosis. *IS&T/SPIE 1993 International Symposium on Electronic Imaging*.

### NCCTG Lung Cancer

- 原始 228 行；本示例保留 168 个完整病例；男性 104、女性 64；事件 121。
- 来源：R 包 `survival` 的 `cancer` 数据集（North Central Cancer Treatment Group, NCCTG），<https://cran.r-project.org/package=survival>。
- 字段：`time`（天）、`event`（1=死亡，0=删失）、`age`、`sex`（1=男，2=女）、`ph.ecog`、`ph.karno`、`pat.karno`、`meal.cal`、`wt.loss`。样本 ID 重新编号为 `L001...`。
- 引用：Loprinzi, C.L. et al. (1994). Prospective evaluation of prognostic variables from patient-completed questionnaires. *Journal of Clinical Oncology*, 12(3), 601–607. <https://doi.org/10.1200/JCO.1994.12.3.601>

### vegan::mite（泥炭沼泽甲螨）

- 70 个样本 × 35 个甲螨类群；`mite.env` 提供 `Shrub`、`Substrate`、`Topo`、`WatrCont`、`SubsDens`。
- 来源：R 包 `vegan` 的 `mite` / `mite.env` 数据集，CRAN: <https://cran.r-project.org/package=vegan>。
- `Shrub` 原始取值为 `None`、`Few`、`Many`；`None` 在 BioPipe CSV Reader 中会被当作缺失，示例将其映射为 `NoShrub`（19/26/25 个样本）。这是读取层适配，不是原始分组变化。
- 引用：Borcard, D., Legendre, P., & Drapeau, P. (1992). Partialling out the spatial component of ecological variation. *Ecology*, 73(3), 1045–1055. <https://doi.org/10.2307/1940179>。

## 组合方式

任务 YAML 是扁平的算子 DAG。示例把 route 中的算子直接展开为多个分支，而不是在 YAML 里引用 route ID：

- `cancer_diagnosis_ml`：`compare_groups` 之后并行 `volcano`、`ma_plot`、`heatmap`；同一特征矩阵再进入 `random_forest_classifier`，最后 `describe`。
- `lung_regression_survival`：`ridge_regression` 回归年龄；`kaplan_meier`、`logrank_test`、`cox_regression` 共享临床表；`forest_plot` 汇总 Cox 结果。
- `mite_community_ml`：`diversity` 与 `distance_matrix` + `reduce` 两个分支；`permanova`、`envfit` 共享距离/坐标；同一丰度矩阵再进入 `random_forest_classifier`，最后 `describe`。PCoA 图使用无着色散点，因为 `join` 输出会丢失 component 标签，`scatter` 无法安全接收带元数据的坐标。

Studio 中可以把这些任务作为图导入，再拆分、合并或替换分支。逐步解释、指标和限制见各目录的 `ANALYSIS.md`。

## 测试

`tests/test_route_combinations.py` 对三个示例执行：

1. `--check` 静态校验；
2. 复制到临时目录后实际运行，检查 `output/run_summary.json` 的状态与步骤数。

测试不会写入仓库内的 `output/`，避免把运行产物或绝对路径带进可移植性审计。
