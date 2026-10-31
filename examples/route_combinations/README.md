# 路线组合示例

本目录把 BioPipe 的多条内置路线组合成可直接运行的分析任务。示例**只使用已有算子与 Reader**，不新增注册项，因此 registry 仍为 402 个算子、85 个 Reader、21 条 route。

## 示例

| 目录 | 组合的路线 | 数据与目的 |
|---|---|---|
| `cancer_diagnosis_ml/` | 差异分析 + 可视化 + 机器学习分类 | UCI 乳腺癌诊断数据；比较良恶性特征差异，并用随机森林做良恶性分类 |
| `lung_regression_survival/` | 回归 + 生存分析 + 可视化 | NCCTG 肺癌数据；用生理指标回归年龄，并做性别分层 KM、log-rank 与 Cox 分析 |
| `mite_community_ml/` | 群落多样性 + 排序/环境拟合 + 机器学习分类 | `vegan::mite` 泥炭沼泽甲螨数据；alpha 多样性、Bray-Curtis PCoA、PERMANOVA/envfit，以及随机森林预测灌木覆盖 |
| `diabetes_classification_regression/` | 机器学习分类 + 机器学习回归 + PCA 可视化 | scikit-learn diabetes 数据；用同一组基线特征同时预测高/低进展组与连续进展值，并用 PCA 观察分组重叠 |
| `pbc_competing_survival/` | 生存分析 + 竞争风险 | `survival::pbc` 原发性胆汁性胆管炎数据；性别分层 KM、Cox、CIF 与 Fine-Gray 竞争风险模型 |
| `birthwt_risk_factors/` | 差异比较 + 逻辑回归 + 随机森林 + PCA/相关热图 | `MASS::birthwt` 低出生体重数据；比较母亲基线、估计风险因素方向、评估分类并检查特征结构 |
| `wine_cultivar_classification/` | 线性判别 + 随机森林 + PCA/相关热图 | UCI Wine 数据；比较 LDA 与随机森林的品种分类，检查线性判别边界、无监督分离与化学特征相关结构 |
| `mtcars_regression_classification/` | 回归 + 分类 + 结构探索 | R datasets::mtcars 1974 年汽车数据；用重量/马力等预测油耗、判断变速箱类型，并用 PCA 与 Spearman 热图看共线结构 |

八个示例都使用公开、可引用的数据集，而不是临时合成数据。数据已放在各自的 `input/` 下，便于离线复现。

## 运行

在项目根目录执行：

    python scripts/run.py examples/route_combinations/cancer_diagnosis_ml
    python scripts/run.py examples/route_combinations/lung_regression_survival
    python scripts/run.py examples/route_combinations/mite_community_ml
    python scripts/run.py examples/route_combinations/diabetes_classification_regression
    python scripts/run.py examples/route_combinations/pbc_competing_survival
    python scripts/run.py examples/route_combinations/birthwt_risk_factors
    python scripts/run.py examples/route_combinations/wine_cultivar_classification
    python scripts/run.py examples/route_combinations/mtcars_regression_classification

只做静态校验：

    python scripts/run.py examples/route_combinations/cancer_diagnosis_ml --check
    python scripts/run.py examples/route_combinations/lung_regression_survival --check
    python scripts/run.py examples/route_combinations/mite_community_ml --check
    python scripts/run.py examples/route_combinations/diabetes_classification_regression --check
    python scripts/run.py examples/route_combinations/pbc_competing_survival --check
    python scripts/run.py examples/route_combinations/birthwt_risk_factors --check
    python scripts/run.py examples/route_combinations/wine_cultivar_classification --check
    python scripts/run.py examples/route_combinations/mtcars_regression_classification --check

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

### scikit-learn diabetes

- 442 个样本、10 个基线特征；目标为疾病进展指标；中位数 140.0，派生 `high` 223 例、`low` 219 例。
- 来源：scikit-learn `sklearn.datasets.load_diabetes`，<https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_diabetes.html>。
- 引用：Efron, B., Hastie, T., Johnstone, I., & Tibshirani, R. (2004). Least Angle Regression. *Annals of Statistics*, 32(2), 407–499.
- 说明：分类标签由目标中位数派生，仅用于演示；不是独立临床诊断标签。

### survival::pbc（原发性胆汁性胆管炎）

- 418 个样本；`status` 为 232 删失 / 25 肝移植 / 161 死亡；女性 374、男性 44。
- 来源：R 包 `survival` 的 `pbc` 数据集，<https://cran.r-project.org/package=survival>。
- 字段：`time`（天）、`status`（0=删失，1=肝移植，2=死亡）、`death`（status==2）、`age`、`sex`、`sex_code`（女=0，男=1）、`bili`、`albumin`、`edema`。样本 ID 重新编号为 `P001...`。
- 引用：Therneau, T.M. & Grambsch, P.M. (2000). *Modeling Survival Data: Extending the Cox Model*. Springer。

### MASS::birthwt（低出生体重）

- 189 例单胎出生记录；低出生体重 59、正常 130；无缺失。
- 来源：R 包 `MASS` 的 `birthwt` 数据集，<https://cran.r-project.org/package=MASS>。原始研究地点为 Baystate Medical Center（Springfield, MA）。
- 字段：`low`、`age`、`lwt`、`race`、`smoke`、`ptl`、`ht`、`ui`、`ftv`；本示例不使用 `bwt` 作为预测特征。`race` 按 race=1 为参照构造 `race_2`、`race_3` 两个指示变量；race 是社会经济/群体变量，不能作生物学解释。
- 引用：Hosmer, D.W. & Lemeshow, S. (2000). *Applied Logistic Regression*, 2nd ed. Wiley；R 包来源 Venables, W.N. & Ripley, B.D. (2002). *Modern Applied Statistics with S*, 4th ed. Springer。

### UCI Wine（三个品种的化学特征）

- 178 个样本、13 个连续化学特征；品种分布 cultivar_1 = 59、cultivar_2 = 71、cultivar_3 = 48；无缺失。
- 来源：UCI Machine Learning Repository, Wine Data Set，<https://archive.ics.uci.edu/dataset/109/wine>；本示例通过 scikit-learn 的 load_wine 读取打包副本。
- 样本 ID 重新编号为 wine_001...wine_178；标签写为 cultivar_1/2/3，类别编码 0/1/2 单独保留。
- 原始提供者：Forina, M. et al., PARVUS - An Extendible Package for Data Exploration, Classification and Correlation。该数据用于方法演示，不构成品种鉴定或质量控制结论。

### datasets::mtcars（1974 Motor Trend 汽车数据）

- 32 辆汽车、11 个变量；本示例用 9 个特征（cyl、disp、hp、drat、wt、qsec、vs、gear、carb），目标为 mpg 与 am（0=自动挡 19 辆，1=手动挡 13 辆）。
- 来源：R datasets 包的 mtcars 数据集，<https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/mtcars.html>；样本 ID 使用车型名。
- 引用：Henderson, H.V. & Velleman, P.F. (1981). Building multiple regression models interactively. Biometrics, 37(2), 391–411. 原始数据由 Motor Trend 1974 年收集。
- 该数据是经典的小样本回归/分类教学数据；32 辆、8 辆测试集，结果只作方法演示，不作现代车辆结论。

## 组合方式

任务 YAML 是扁平的算子 DAG。示例把 route 中的算子直接展开为多个分支，而不是在 YAML 里引用 route ID：

- `cancer_diagnosis_ml`：`compare_groups` 之后并行 `volcano`、`ma_plot`、`heatmap`；同一特征矩阵再进入 `random_forest_classifier`，最后 `describe`。
- `lung_regression_survival`：`ridge_regression` 回归年龄；`kaplan_meier`、`logrank_test`、`cox_regression` 共享临床表；`forest_plot` 汇总 Cox 结果。
- `mite_community_ml`：`diversity` 与 `distance_matrix` + `reduce` 两个分支；`permanova`、`envfit` 共享距离/坐标；同一丰度矩阵再进入 `random_forest_classifier`，最后 `describe`。PCoA 图使用无着色散点，因为 `join` 输出会丢失 component 标签，`scatter` 无法安全接收带元数据的坐标。
- `diabetes_classification_regression`：`random_forest_classifier` 与 `ridge_regression` 共享同一特征/标签表；`pca` + `join` + `scatter` 提供无监督分组视图。
- `pbc_competing_survival`：`kaplan_meier`/`logrank_test`/`cox_regression` 共享同一临床表；`cumulative_incidence` 与 `fine_gray` 把肝移植作为竞争事件，分别给出绝对风险和子分布风险。
- `birthwt_risk_factors`：`compare_groups` 比较两组母亲年龄/体重；`logistic_regression` 与 `random_forest_classifier` 共享 9 个基线特征；`pca` + `join` + `scatter` 观察分组重叠；`correlation` + `heatmap` 检查风险因素相关结构。逻辑回归的 OR 是描述性近似，不输出标准误/P 值/CI。

- `wine_cultivar_classification`：`lda_classifier` 与 `random_forest_classifier` 共享同一特征/标签和固定划分；`pca` + `join` + `scatter` 检查无监督分离；`correlation` + `heatmap` 检查 13 个化学特征的共变。LDA 的 1.0 测试准确率只代表这份小数据，不当作泛化证据。
- `mtcars_regression_classification`：compare_groups 比较自动/手动挡的 mpg、wt、hp；ridge_regression 用 9 个特征预测 mpg；logistic_regression 与 random_forest_classifier 用同一组特征预测 am；pca + join + scatter 看变速箱分组；correlation + heatmap 看 10 个变量的共线结构。

Studio 中可以把这些任务作为图导入，再拆分、合并或替换分支。逐步解释、指标和限制见各目录的 `ANALYSIS.md`。

## 测试

`tests/test_route_combinations.py` 对八个示例执行：

1. `--check` 静态校验；
2. 复制到临时目录后实际运行，检查 `output/run_summary.json` 的状态与步骤数。

测试不会写入仓库内的 `output/`，避免把运行产物或绝对路径带进可移植性审计。
