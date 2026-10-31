## 0.103.0 — 2026-10-31

- 新增 `hierarchical_clustering` 层次聚类：一个 `[sample,feature]` 数值表，支持 single/complete/average/Ward.D2 连接与 euclidean/manhattan 距离；输出 0-based cluster 标签，info/export 提供 heights、merge 与 cophenetic correlation。
- 算子总数 **402**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 402/85，registry `errors []`；Machine Learning 类别 61→62。
- 验证：`tests/test_hierarchical_clustering.py` 3 项 + `tests/test_r_oracles83.py` 1 项 = **4 passed**；R `stats::hclust` 对 6×2 fixture 的四种连接 heights、k=3 标签与 cophenetic correlation 对齐（heights/coph atol 1e-12）；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：拒绝非有限值；不做缺失值插补；不生成树状图；不实现 bootstrap/consensus 聚类。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.102.0 — 2026-10-31

- 新增 `conditional_logistic` 条件 logistic 回归：一个 `[sample,feature]` 表提供分层变量、二分类结局与一个或多个数值协变量；按层消去截距的精确条件似然，Newton-Raphson 拟合，观测信息矩阵标准误。
- 输出 `[term,statistic]` 的 `coef,se,z,P,CI_low,CI_high,OR`；info 含 `n/n_strata/n_cases/n_controls/loglikelihood/converged/iterations/levels`；export 含 OR 与计数。
- 算子总数 **401**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 401/85，registry `errors []`；Statistics 类别 236→237。
- 验证：`tests/test_conditional_logistic.py` 3 项 + `tests/test_r_oracles82.py` 1 项 = **4 passed**；R `survival::clogit` 对 n=120（60 对，seed 20261123）的 coef/SE atol 1e-6、loglik atol 1e-8；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：仅数值协变量；每个分层需同时有病例与对照；不实现分层精确检验、条件 Poisson、稳健方差或新样本预测；1:1 与 1:m 匹配均可。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.101.0 — 2026-10-31

- 新增 `interval_censored_regression` 区间删失 Weibull AFT 回归：一个 `[sample,feature]` 表提供区间下界/上界与一个或多个数值自变量；上界 `Inf` 表示右删失、下界 0 表示左删失、上下界相等表示精确时间；Weibull AFT 区间似然，数值 Hessian 标准误。
- 输出 `[term,statistic]` 的 `coef,se,z,P,CI_low,CI_high`，term 为截距、自变量与 `log_scale`；info 含 `scale/shape/loglik`、`n_exact/n_interval/n_right/n_left`、`converged/iterations`；export 含逐样本上下界与系数。
- 算子总数 **400**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 400/85，registry `errors []`；Statistics 类别 235→236。
- 验证：`tests/test_interval_censored_regression.py` 3 项 + `tests/test_r_oracles81.py` 1 项 = **4 passed**；R `survival::survreg(Surv(lower, upper, type="interval2") ~ x1 + x2, dist="weibull")` 对 n=160 fixture 的 coef/SE/log_scale/loglik atol 1e-5；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：仅 Weibull AFT；不实现 Turnbull 非参数估计、时变协变量、frailty 或其他分布；不做新样本预测；左删失下界为 0，右删失上界为 Inf。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.100.0 — 2026-10-31

- 新增 `additive_glm` 可加 B 样条 GLM：一个 `[sample,feature]` 表包含响应与 2–8 个自变量；支持 `binomial`（logit）与 `poisson`（log）族；逐自变量 `patsy.bs(..., degree=3, include_intercept=False)` 基 + 截距，`statsmodels` GLM 拟合。
- 输出 `[sample,statistic]` 的 `y,linear_predictor,fitted,residual,se_mean,ci_low,ci_high`；info 含 `family/link/terms/confidence/n/n_basis/deviance/null_deviance/pseudo_r2/aic/converged`；export 含系数、项信息、拟合与区间。
- 算子总数 **399**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 399/85，registry `errors []`；Statistics 类别 234→235。
- 验证：`tests/test_additive_glm.py` 4 项 + `tests/test_r_oracles80.py` 2 项 = **6 passed**；R `glm(y ~ splines::bs(x1, df=4) + splines::bs(x2, df=4), family=binomial/poisson)` 对 fitted/link 逐值 atol 1e-8；增量门 **22 passed**；`-W error` **8 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：可加模型，不估计平滑参数、不建模交互项、不提供新样本预测；仅数值自变量与二项/泊松族；二项响应必须恰有两个水平（0/1 或映射为 0/1），泊松响应必须为非负整数计数；无 R 之外的外部实现对照。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.99.0 — 2026-10-31

- 新增 `envfit` 环境向量拟合：排序坐标 `[sample,component]` 与环境变量 `[sample,feature]` 按样本标签对齐；逐变量 OLS 得到 R²，回归系数单位化后作为环境梯度方向；输出 `r2,axis1..axisK` 与方向向量。
- 算子总数 **398**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 398/85，registry `errors []`；Statistics 类别 233→234。
- 验证：`tests/test_envfit.py` 3 项 + `tests/test_r_oracles79.py` 1 项 = **4 passed**；R `vegan::envfit` 对 n=30 fixture 的 R²/方向向量逐值一致；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：只做线性环境向量拟合，不计算置换 p 值，不支持因子型 envfit 或非线性环境曲面；方向向量为单位长度。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.98.0 — 2026-10-31

- 新增 `additive_spline_regression` 可加 B 样条回归：多个自变量的三次 B 样条基 + OLS，输出拟合/残差/均值标准误/置信区间；支持逐特征 `df` 映射；R `splines::bs` 对照。
- 算子总数 **397**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 397/85，registry `errors []`；Statistics 类别 232→233。
- 验证：`tests/test_additive_spline_regression.py` 3 项 + `tests/test_r_oracles78.py` 1 项 = **4 passed**；R² **0.996115600178689**；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：可加模型，不估计平滑参数；不建模交互项；2–8 个自变量；不提供新样本预测。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.97.0 — 2026-10-31

- 新增 `gaussian_process_regressor` 高斯过程回归：固定 RBF 核与观测噪声，不做边际似然优化；输出观测/拟合/残差/后验标准误，info 记录 R²、RMSE 与 log marginal likelihood；闭式 GP 公式手算对照。
- 算子总数 **396**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 396/85，registry `errors []`；Machine Learning 类别 60→61。
- 验证：`tests/test_gaussian_process_regressor.py` 3 项 = **3 passed**；闭式后验均值/标准误 atol 1e-10；增量门 **19 passed**；`-W error` **5 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：仅固定核超参数、单输出、数值自变量；不提供新样本预测、分类 GP 或核超参数优化。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.96.0 — 2026-10-31

- 新增 `vecm` 向量误差修正模型：Johansen trace/eigenvalue 诊断 + statsmodels VECM 系数；输出所有秩的 trace/eigen 与所选秩的 beta/alpha；R `urca::ca.jo(ecdet="none", K=k_ar_diff+1)` 对照。
- 算子总数 **395**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 395/85，registry `errors []`；Statistics 类别 231→232。
- 验证：`tests/test_vecm.py` 2 项 + `tests/test_r_oracles77.py` 1 项 = **3 passed**；R trace/eigen 逐值一致，beta/alpha 容差 2e-3；增量门 **19 passed**；`-W error` **5 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：仅无确定性项、无外生变量/季节项；`coint_rank` 必须 1..变量数-1；不提供预测、IRF 或自动定阶。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.95.0 — 2026-10-31

- 新增 `spline_regression` B 样条回归：`patsy.bs` 三次 B 样条基 + OLS，输出拟合值、残差、均值标准误与置信区间；`df` 4–10，R `splines::bs` 对照。
- 算子总数 **394**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 394/85，registry `errors []`；Statistics 类别 230→231。
- 验证：`tests/test_spline_regression.py` 3 项 + `tests/test_r_oracles76.py` 1 项 = **4 passed**；R fitted/residual 误差 < 1e-8，R² 容差 1e-10；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：单自变量、无外生变量/权重/稳健方差；丢弃非有限行；`n >= df+2`、设计矩阵不得秩亏；不提供新样本预测或自动选 df。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.94.0 — 2026-10-31

- 新增 `box_cox` Box-Cox 变换：逐特征 MLE 估计 lambda，也支持固定标量/按特征映射；`shift` 可把非正数据平移到正域；缺失值保留，输出同维表。
- 算子总数 **393**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 393/85，registry `errors []`；Data 类别 35→36，Statistics 保持 230。
- 验证：`tests/test_box_cox.py` 5 项 + `tests/test_r_oracles75.py` 1 项 = **6 passed**；R `MASS::boxcox` lambda 对照；增量门 **22 passed**；`-W error` **8 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：仅 2D 数值表；正性、每特征至少 3 个有限值、lambda 键/数值合法性均严格检查；不提供置信区间或自动反变换。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.93.0 — 2026-10-31

- 新增 `probit_regression` 概率单位回归：一个二分类响应表，`response_label` + `predictors`，隐式截距，支持可选 `categorical`；输出系数/标准误/z/p/置信区间，info 记录 loglik、AIC 与 pseudo-R²。
- 算子总数 **392**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 392/85，registry `errors []`；Statistics 类别 229→230。
- 验证：`tests/test_extension86.py` 3 项 + `tests/test_r_oracles74.py` 1 项 = **4 passed**；R `glm(family=binomial(link="probit"))` 逐值对照（coef/SE 3e-5）；增量门 **20 passed**；`-W error` **7 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：仅二分类、无权重/偏移/稳健方差；字符串响应需先编码为数值；水平数不为 2、响应列同时作预测列、缺失预测列或秩亏时报错。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.92.0 — 2026-10-31

- 新增 `sarima` 季节性 ARIMA：支持 `(p,d,q)(P,D,Q,s)`、常数趋势、置信区间；输出系数/标准误/z/p/CI 与 sigma2、loglik、AIC/BIC、阶数和样本数。
- 算子总数 **391**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 391/85，registry `errors []`；Statistics 类别 228→229。
- 验证：`tests/test_extension85.py` 2 项 + `tests/test_r_oracles73.py` 1 项 = **3 passed**；R `stats::arima` 季节模型逐值对照（系数/SE 1e-4，AIC 2e-3）；增量门 **19 passed**；`-W error` **5 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：单变量、等间隔、无外生变量/缺失时间戳；不提供预测、季节分解或自动定阶；拒绝全季节阶数为 0 与非平稳常数趋势组合。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.91.0 — 2026-10-31

- 新增 `nmds`（非度量多维尺度分析）：一个对称距离矩阵，SMACOF + classical-MDS 确定性起点，输出样本坐标与 raw stress / Kruskal stress1；轴符号固定，重复运行一致。
- 算子总数 **390**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 390/85，registry `errors []`。
- 验证：`tests/test_extension83.py` 4 项 = **4 passed**；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：R `MASS::isoMDS` 与非度量 SMACOF 在非欧矩阵上收敛到不同局部最优（stress 21.32521% vs 25.45%），不做逐值 oracle；仅用欧氏/一维 fixture 验证 stress≈0、距离秩相关与确定性。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.90.0 — 2026-10-31

- 新增 `fine_gray`（Fine-Gray 竞争风险子分布回归）：一个 `[sample,feature]` 表，`time_label`/`event_label`/`covariates` 必填；加权子分布风险部分似然、Breslow ties、Newton + 线搜索，稳健 sandwich 协方差；输出系数、HR、SE、z/P/CI 与事件/竞争/删失计数。
- 算子总数 **389**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 389/85，registry `errors []`。
- 验证：`tests/test_extension82.py` 4 项 + `tests/test_r_oracles72.py` 1 项 = **5 passed**；R `cmprsk::crr` n=240 对照系数 **0.946618077 / -0.426474219**、稳健 SE **0.109809053 / 0.092094486**、loglik **-502.880098**；增量门 **21 passed**；`-W error` **7 passed**；frontend **39 passed / 9 files**，构建通过。
- 边界：只支持右删失 + 竞争风险；不提供时变协变量、分层基线或预测曲线；无竞争事件路径有测试，但不声明等价于 cause-specific Cox。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.89.0 — 2026-10-31

- 新增 `bai_perron`（Bai-Perron 多结构突变回归）：固定断点数的动态规划分段 OLS，输出分段系数、1-based 断点、RSS 与 BIC；R `strucchange::breakpoints` 对照。
- 算子总数 **388**，Reader 仍 **85**，路线 **21**，provider 包 **6**；参考页 388/85，registry `errors []`。
- 验证：新增 4 项（3 手算 + 1 R oracle）通过；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files** 且构建通过。

## 0.88.0 — 2026-10-31

- 新增：`dca`（决策曲线分析）与 `lowess`（局部加权散点平滑）两个统计算子；算子总数 **387**，Reader 仍 **85**。
- 许可证：项目整体切换为 **Apache License 2.0**，新增 `LICENSE`/`NOTICE`，移除旧专有许可与商业授权表述；Python 与前端包元数据同步为 `Apache-2.0`。
- 验证：`tests/test_extension80.py` 5 项 + `tests/test_r_oracles70.py` 2 项 = **7 passed**；R 对照 `dcurves::dca`、`stats::lowess`；增量门 **25 passed**；`-W error` **9 passed**；frontend **39 passed / 9 files**，构建通过。
- 修复/边界：发现 `chow_test` 已在 0.25 引入并恢复原文件，未重复新增；DCA 阈值上限 1000、拒绝非 0/1 结局；LOWESS 拒绝少于 3 点与常数 x。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.87.0 — 2026-10-31

- 新增：`arima`（非季节 ARIMA 时间序列模型）与 `isotonic`（保序/单调回归）两个统计算子；算子总数 **385**，Reader 仍 **85**。
- 验证：`tests/test_extension79.py` 5 项 + `tests/test_r_oracles69.py` 2 项 = **7 passed**；R 对照 `stats::arima(method="ML")` 与 `isoreg`；增量门 **28 passed**；`-W error` **9 passed**；frontend **39 passed / 9 files**，构建通过。
- 修复/边界：ARIMA 的 statsmodels 默认 OPG 标准误与 R Hessian 不一致，显式改用 `cov_type="approx"`；ARIMA 拒绝 `p+q=0`、`d>0` 带常数趋势、短序列与零方差；isotonic 拒绝重复 x、少于 3 个有限点与非零 x 范围。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.86.0 — 2026-10-31

- 新增：`chao1`（Chao1 物种丰富度估计）与 `rarefaction`（个体稀疏化）两个微生物/生态多样性算子；算子总数 **383**，Reader 仍 **85**。
- 验证：`tests/test_extension78.py`/`tests/test_r_oracles68.py` 共 **6 passed**；R 对照 `vegan::estimateR`、`vegan::rarefy`；增量门 **22 passed**；`-W error` **8 passed**；frontend **39 passed / 9 files**。
- 修复：rarefaction `depth==N` 边界；Chao1/rarefaction 严格拒绝负数和浮点计数。
- 说明：本版未运行全量 pytest；最近全量为 0.84 **974 passed, 1 skipped**。核心执行层不变。

## 0.85.0 — 2026-10-31

- 新增：`aft`（Weibull 加速失效时间/右删失生存回归）与 `hardy_weinberg`（精确双等位 HWE 检验）；算子总数 **381**，Reader 仍 **85**。
- 验证：`tests/test_extension77.py`/`tests/test_r_oracles67.py` 共 **6 passed**；R 对照 `survival::survreg`、`HardyWeinberg::HWExact`；增量门 **100 passed**；`-W error` **8 passed**；frontend **39 passed / 9 files**。
- 文档：新增 9 个系统对象参考页（Form/Task/Graph/Project/Reader/Step/Runner/Registry/SDK），并接入 docs/reference 索引；未改核心执行层。
- 修复：HWE 尾概率比较去掉绝对 epsilon（极端 p 不再被放大）；AFT 的 R 参考项 `(Intercept)` 映射。

## 0.84.0 — 2026-10-31

- 重构：算子分类收敛为 **6 个英文首字母大写类别**（Data / Statistics / Machine Learning / Omics / Visualization / Quality Control）；分类在 `build_catalog` 归一，注册表保存机器分类，前端只做显示映射。
- 新增：每个算子/Reader 的 title/description/category/platforms 进入 manifest 与 SDK `Descriptor`；算子库卡片、Reader 库、Inspector 功能预览展示描述、输入输出、扩展名与“Windows 不可用”标记。
- 自动检查：新增 `tests/test_catalog_integrity.py`，对比注册表与 `discover_steps()`/`discover_readers()`，防止新模块漏检；前端测试强制所有算子/Reader 有分类、标题、描述，并覆盖 Reader 卡片渲染。
- 修复：`tenx_h5_reader.py` 导入的 `CsvReader` 曾被误计入 Reader 集合（86→85）；`youden_index.py` 的 UTF-8 BOM 曾使注册表静态解析失败；均已修正。
- 验证：分类/目录定向测试 **20 passed**；Studio 前端 **39 passed（9 files）**，构建通过；registry clean **379/85/21/6**。全量 pytest：**974 passed, 1 skipped**。
- 计数口径：前端按 Vitest 实际用例数记录；此前 changelog 的累计口径不再作为覆盖审计依据。

## 0.83.0 — 2026-10-31

- 新增：379 算子 / 85 Reader / 21 route；新增距离基冗余分析（db-RDA）与留一研究 Meta 分析两个多元/证据综合算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension76.py` 7 项、`tests/test_r_oracles66.py` 2 项，合计 **9 passed**；R 对照 `vegan::dbrda`、`metafor::leave1out`；registry clean；参考页 379/85；增量门 25 passed；`-W error` 11 passed；Studio 前端 325 passed。
- 边界：`dbrda` 只支持 Bray-Curtis/欧氏距离，要求响应非负且每样本行和为正，解释变量中心化后满秩；`leave_one_out` 仅重拟合截距模型，要求研究标签唯一、效应/方差有限、方差为正、至少 3 项研究。

## 0.82.0 — 2026-10-31

- 新增：377 算子 / 85 Reader / 21 route；新增主坐标分析（PCoA）与典范对应分析（CCA）两个排序算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension75.py` 5 项、`tests/test_r_oracles65.py` 2 项，合计 **7 passed**；R 对照 `vegan::cmdscale`、`vegan::cca`；registry clean；参考页 377/85；增量门 22 passed（另 1 skipped）；`-W error` 11 passed；Studio 前端 323 passed。
- 边界：PCoA 拒绝非方阵/非对称/非零对角/负距离，只保留正特征值；CCA 要求计数非负、行列为正、响应样本与解释变量样本一致，解释变量秩≥1，且样本数大于解释变量数；CCA 只输出约束轴，未约束惯量在 info 中报告。

## 0.81.0 — 2026-10-31

- 新增：375 算子 / 85 Reader / 21 route；新增逆高斯回归、beta 离散度齐性检验、零膨胀负二项回归；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension74.py` 6 项、`tests/test_r_oracles64.py` 3 项，合计 **9 passed**；R 对照 `stats::glm`、`vegan::betadisper`、`pscl::zeroinfl`；registry clean；参考页 375/85；增量门 25 passed；`-W error` 11 passed；Studio 前端 321 passed。
- 边界：逆高斯只支持 log link；AIC 与 R 的 likelihood 常数不同，R oracle 只比较 coef/se；betadisper 只做 centroid 距离；ZINB 只支持 NB2，count 与 zero 预测变量均必填。

## 0.80.0 — 2026-10-31

- 新增：372 算子 / 85 Reader / 21 route；新增 GSEA `.rnk` 排名列表与 `.cls`/`.grp` 表型标签三个 Reader；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension73.py` 7 项，合计 **7 passed**；格式 Reader 使用黄金文件与严格负例，无 R oracle；registry clean；参考页 372/85；增量门 23 passed；Studio 前端 318 passed（无新增算子）。
- 边界：RNK 保留排名顺序，重复基因/非有限分数拒绝；CLS/GRP 共享严格计数与类别索引解析，类别名经 label encoder 记录，`group_values` 可还原；类别名含空格需按 GSEA 规范预处理。

## 0.79.0 — 2026-10-31

- 新增：372 算子 / 82 Reader / 21 route；新增逆方差固定/随机效应 Meta 回归（`meta_regression`）；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension72.py` 4 项、`tests/test_r_oracles63.py` 1 项，合计 **5 passed**；R 对照 `metafor` 固定效应与 DL 随机效应；registry clean；参考页 372/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 318 passed。
- 边界：一个 `[study,feature]` 表，效应量/方差/moderators 必须为数值列；隐式截距；random 仅 DL，tau2 分母用 `tr(P)`；不做置换检验、发表偏倚或网状 Meta。

## 0.78.0 — 2026-10-31

- 新增：371 算子 / 82 Reader / 21 route；新增 Beta 回归与冗余分析（RDA）两个回归/约束排序算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension71.py` 5 项、`tests/test_r_oracles62.py` 2 项，合计 **7 passed**；R 对照 `betareg`、`vegan`；registry clean；参考页 371/82；增量门 23 passed；`-W error` 11 passed；Studio 前端 317 passed。
- 边界：Beta 回归要求响应严格在 (0,1)，均值 logit、精度 identity，SE 用 statsmodels EIM 协方差；不处理 0/1 膨胀。RDA 只做线性约束排序，不提供置换显著性；惯量除以 n−1，与 vegan 一致；响应/解释矩阵秩亏或样本不足会拒绝。

## 0.77.0 — 2026-10-31

- 新增：369 算子 / 82 Reader / 21 route；新增 t 检验、两比例检验、单因素 ANOVA 三个功效/样本量计算算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension70.py` 4 项、`tests/test_r_oracles61.py` 1 项，合计 **5 passed**；R 对照 `pwr`；registry clean；参考页 369/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 315 passed。
- 边界：三算子只计算给定设计下的 achieved power，不反解样本量；两比例用 Cohen h 正态近似；ANOVA 只支持平衡设计；无输入计算算子。

## 0.76.0 — 2026-10-31

- 新增：366 算子 / 82 Reader / 21 route；新增 GARCH 波动率模型与向量自回归（VAR）两个时间序列算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension69.py` 4 项、`tests/test_r_oracles60.py` 1 项，合计 **5 passed**；GARCH 用 `arch` 8.0.0，VAR 用 R `vars::VAR`；registry clean；参考页 366/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 312 passed。
- 修复：`VarModelStep` 误把 `table_frame` 的 `__sample__` 列纳入特征，导致所有行被数值化丢弃；现在先排除该内部列，再检查至少两个序列。
- 边界：GARCH 只实现常均值/零均值 GARCH，不实现 EGARCH/GJR/ARCH-in-mean；VAR 只输出简约式系数，不提供 IRF/FEVD/结构识别。

## 0.75.0 — 2026-10-31

- 新增：364 算子 / 82 Reader / 21 route；新增对应分析（CA）与 Tobit 左删失回归两个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension68.py` 4 项、`tests/test_r_oracles59.py` 1 项，合计 **5 passed**；R 对照 `ca::ca`、`censReg`；registry clean；参考页 364/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 310 passed。
- 边界：CA 要求非负计数表且行/列边际为正，`n_components` 自动截断；输出坐标/贡献/cos2，不画图。Tobit 只做左删失、隐式截距；全删失/秩亏/样本不足会拒绝；SE 为数值 Hessian，不提供稳健 SE。

## 0.74.0 — 2026-10-31

- 新增：362 算子 / 82 Reader / 21 route；新增 CUSUM 与 EWMA 个体测量控制图两个统计过程控制算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension67.py` 4 项、`tests/test_r_oracles58.py` 1 项，合计 **5 passed**；R 对照 `qcc::cusum`、`qcc::ewma`；registry clean；参考页 362/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 308 passed。
- 边界：两个算子都只处理一个 `value_label` 序列；sigma 用平均移动极差 / 1.128 估计；CUSUM 使用 `decision_interval` 与 `se_shift`，EWMA 使用 `lambda` 与 `nsigmas`；输出为表格，不直接画图；常数序列被拒绝。

## 0.73.0 — 2026-10-31

- 新增：360 算子 / 82 Reader / 21 route；新增 Phillips-Perron 单位根、DF-GLS 单位根、Engle ARCH LM 波动检验三个时间序列诊断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension66.py` 4 项、`tests/test_r_oracles57.py` 1 项，合计 **5 passed**；R 对照 `urca::ur.pp`、`urca::ur.ers`、`FinTS::ArchTest`；registry clean；参考页 360/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 306 passed。
- 边界：`phillips_perron` 使用 arch 的 Z-tau，`lags=null` 时 AIC 选滞后；与 R `ur.pp` 的统计量在 1e-6 内一致（长程方差带宽实现不同）。`dfgls` 使用 arch 的 DF-GLS，`lags=null` 时 AIC；固定滞后时与 R `ur.ers` 逐值一致。`arch_lm` 输入按残差处理，不拟合均值模型；依赖 `arch>=6`。

## 0.72.0 — 2026-10-31

- 新增：357 算子 / 82 Reader / 21 route；新增 Theil 不确定系数、标准化 DFBETAS、COVRATIO 三个关联/回归影响算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension65.py` 4 项、`tests/test_r_oracles56.py` 1 项，合计 **5 passed**；R 对照 `DescTools::UncertCoef`、`stats::dfbetas`、`stats::covratio`；registry clean；参考页 357/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 303 passed。
- 边界：Theil U 不含 DescTools 的置信区间；DFBETAS/COVRATIO 需要至少一个预测变量且设计矩阵满秩；输出为 float32 Form。

## 0.71.0 — 2026-10-31

- 新增：354 算子 / 82 Reader / 21 route；新增 Zivot-Andrews 结构突变单位根、精确两样本泊松率检验两个推断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension64.py` 4 项、`tests/test_r_oracles55.py` 1 项，合计 **5 passed**；R 对照 `urca::ur.za` 与 `poisson.test`；registry clean；参考页 354/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 300 passed。
- 边界：Zivot-Andrews 的 `break_index` 为零基 `bpidx`，R `urca` 的 `bpoint` 为一基；泊松率检验使用条件二项精确检验和 exact proportion CI，不使用 scipy E-test；总计数为 0 时 p=1。

## 0.70.0 — 2026-10-31

- 新增：352 算子 / 82 Reader / 21 route；新增 Engle-Granger 残差协整、Johansen 迹/最大特征值协整两个时间序列算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension63.py` 4 项、`tests/test_r_oracles54.py` 1 项，合计 **5 passed**；R 对照 `urca::ur.df` 与 `urca::ca.jo`；registry clean；参考页 352/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 298 passed。
- 边界：EG 仅二元且仅 `aeg` 方法，`trend` 支持 c/ct/ctt，`lags` 可手动或 AIC；Johansen 要求完整样本，`det_order` 为 -1/0/1；临界值来自 statsmodels 表。

# 更新记录

## 0.69.0 — 2026-10-31

- 新增：350 算子 / 82 Reader / 21 route；新增近似熵、简单 R/S Hurst 指数两个非线性序列算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension62.py` 4 项、`tests/test_r_oracles53.py` 1 项，合计 **5 passed**；R 对照 `pracma::approx_entropy` 与 `hurstexp`；registry clean；参考页 350/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 296 passed。
- 边界：近似熵限 1–5 维嵌入、2000 点；Hurst 仅实现简单 R/S，奇数长度按 `hurstexp` 约定补齐。

## 0.68.0 — 2026-10-31

- 新增：348 算子 / 82 Reader / 21 route；新增 Gwet AC1、Brennan-Prediger、Conger kappa 三个未加权评分者一致性系数；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension61.py` 4 项、`tests/test_r_oracles52.py` 1 项，合计 **5 passed**；R 对照 `irrCAC`；registry clean；参考页 348/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 294 passed。
- 边界：输入为一个 `[subject,rater]` 评分矩阵；每名受试者至少 2 个评分；允许缺失；Conger 要求每名评分者至少 2 个评分；仅实现未加权系数。

## 0.67.0 — 2026-10-31

- 新增：345 算子 / 82 Reader / 21 route；新增标准化残差、学生化残差、PRESS 三个 OLS 残差诊断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension60.py` 4 项、`tests/test_r_oracles51.py` 1 项，合计 **5 passed**；三项均对照 R `lm` 的 `rstandard`/`rstudent` 与 PRESS 公式；registry clean；参考页 345/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 291 passed。
- 边界：输入为含响应列的 OLS 设计表；自动加截距、listwise 删除缺失行；要求 `n > p+1` 且设计满秩，杠杆值接近 1 或删除残差方差非正时拒绝。

## 0.66.0 — 2026-10-31

- 新增：342 算子 / 82 Reader / 21 route；新增 OLS 杠杆值、Cook 距离、DFFITS 三个回归影响诊断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension59.py` 4 项、`tests/test_r_oracles50.py` 1 项，合计 **5 passed**；三项均对照 R `lm` 的 `hatvalues`/`cooks.distance`/`dffits`；registry clean；参考页 342/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 288 passed。
- 边界：输入为含响应列的完整 OLS 设计表；自动加截距、listwise 删除缺失行；要求 `n > p+1` 且设计满秩，杠杆值接近 1 或删除残差方差非正时拒绝。

## 0.65.0 — 2026-10-31

- 新增：339 算子 / 82 Reader / 21 route；新增方差比检验、Youden 指数、Krippendorff α 三个推断/一致性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension58.py` 4 项、`tests/test_r_oracles49.py` 1 项，合计 **5 passed**；方差比对照 R `var.test`，Krippendorff 对照标准公式与 R `irr::kripp.alpha` 缺失数据 fixture；registry clean；参考页 339/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 285 passed。
- 边界：方差比要求每组 >=2 且方差非零；Youden 需要二分类标签和连续分数；Krippendorff 支持 nominal/interval 与缺失评分，R `irr` 0.84.1 的完整数据分母 bug 已在 SOP/测试中注明。

## 0.64.0 — 2026-10-31

- 新增：336 算子 / 82 Reader / 21 route；新增风险比、比值比、Cohen's h 三个 2×2 表效应量算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension57.py` 4 项、`tests/test_r_oracles48.py` 1 项，合计 **5 passed**；RR/OR 对照 R 公式与 `epitools`，Cohen's h 对照 `pwr::ES.h`；registry clean；参考页 336/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 282 passed。
- 边界：输入为非负 2×2 计数表；RR 第 1 行暴露、第 2 行非暴露；零格默认 Haldane +0.5，可关闭；OR 为 `a*d/(b*c)`，Cohen's h 使用独立比例的正态 CI。

## 0.63.0 — 2026-10-31

- 新增：333 算子 / 82 Reader / 21 route；新增互相关函数、BDS 非线性依赖、差分符号检验三个时间序列诊断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension56.py` 4 项、`tests/test_r_oracles47.py` 1 项，合计 **5 passed**；CCF/差分符号对照 R，BDS 对照 statsmodels；registry clean；参考页 333/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 279 passed。
- 边界：CCF 要求 `lags < n`；差分符号要求至少两个非零差分；BDS 要求 `max_dim >= 2`、`n >= max_dim + 2`、非常量，epsilon 缺省 0.5×sd。

## 0.62.0 — 2026-10-31

- 新增：330 算子 / 82 Reader / 21 route；新增 Fowlkes-Mallows、同质/完整/V-measure、成对混淆矩阵三个聚类一致性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension55.py` 4 项、`tests/test_r_oracles46.py` 1 项，合计 **5 passed**；FMI/HCV/PCM 用 sklearn 固定参考值，PCM 的 Rand 关系对照 R `aricode::RI`；registry clean；参考页 330/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 276 passed。
- 边界：两个分区都至少 2 簇、至少 2 个共享样本；成对矩阵按 `[[同簇同标签, 同簇异标签], [异簇同标签, 异簇异标签]]`；V-measure 的 beta 必须大于 0。

## 0.61.0 — 2026-10-31

- 新增：327 算子 / 82 Reader / 21 route；新增 ACF、PACF、precision-recall 曲线三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension54.py` 4 项、`tests/test_r_oracles45.py` 1 项，合计 **5 passed**；ACF/PACF 对照 R `stats::acf`/`stats::pacf`，PR 对照 sklearn；registry clean；参考页 327/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 273 passed。
- 边界：ACF 使用 `lags < n`、非常量序列与 Bartlett 置信区间；PACF 使用 Yule-Walker `ywm` 与正态近似；PR 曲线要求至少 4 个共享样本、两类都存在，`drop_intermediate=False`，末尾补 NaN threshold 点。

## 0.60.0 — 2026-10-31

- 新增：324 算子 / 82 Reader / 21 route；新增 Box-Pierce 自相关检验、Stuart-Maxwell 边际齐性检验、变异信息三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension53.py` 4 项、`tests/test_r_oracles44.py` 1 项，合计 **5 passed**；对照 R `stats::Box.test(type="Box-Pierce")`、`DescTools::StuartMaxwellTest`、`aricode::NVI`；registry clean；参考页 324/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 270 passed。
- 边界：Box-Pierce 使用 `n*sum(rho^2)`，要求 `lags < n` 且 `fitdf < lags`；Stuart-Maxwell 使用前 k-1 个边际差与协方差矩阵，剔除对角线同时等于行列边际的类别；变异信息用自然对数，NVI=VI/H(A,B)，两表按共享样本对齐。

## 0.59.0 — 2026-10-31

- 新增：321 算子 / 82 Reader / 21 route；新增 Dunn 指数、调整互信息、逐样本轮廓系数三个聚类验证/一致性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension52.py` 4 项、`tests/test_r_oracles43.py` 1 项，合计 **5 passed**；对照 R `clusterCrit::intCriteria(..., "Dunn")`、`aricode::AMI`、`cluster::silhouette`；registry clean；参考页 321/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 267 passed。
- 边界：Dunn 要求至少 2 簇且每簇至少 2 个样本，簇内直径为零时报错；调整互信息默认 `average_method=max` 以对齐 `aricode::AMI`，也支持 arithmetic/geometric/min；逐样本轮廓与 `silhouette_score` 使用同一欧氏距离和簇约束。

## 0.58.0 — 2026-10-31

- 新增：318 算子 / 82 Reader / 21 route；新增轮廓系数、调整兰德指数、归一化互信息三个聚类验证/一致性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension51.py` 4 项、`tests/test_r_oracles42.py` 1 项，合计 **5 passed**；对照 R `cluster::silhouette` 与 `aricode`；registry clean；参考页 318/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 264 passed。
- 边界：轮廓系数要求至少 2 个簇且每簇至少 2 个样本；ARI/NMI 按共享样本对齐并拒绝缺失标签；NMI 的 arithmetic/geometric/max/min 分别对应 R `aricode` 的 sum/sqrt/max/min。

## 0.57.0 — 2026-10-31

- 新增：315 算子 / 82 Reader / 21 route；新增 Tukey HSD、Tamhane T2、Student-Newman-Keuls 三个全成对均值比较算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension50.py` 4 项、`tests/test_r_oracles41.py` 1 项，合计 **5 passed**；对照 R `PMCMRplus`；registry clean；参考页 315/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 261 passed。
- 边界：每组至少 2 个有限值；Tukey 合并方差、Tamhane Welch df + Sidak、SNK step-down；均为近似分布，不声称精确；SNK 未做单调化。

## 0.56.0 — 2026-10-31

- 新增：312 算子 / 82 Reader / 21 route；新增 Chacko 有序备择、Fligner-Wolfe 对照比较、Mack-Wolfe 伞形检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension49.py` 4 项、`tests/test_r_oracles40.py` 1 项，合计 **5 passed**；对照 R `PMCMRplus`；registry clean；参考页 312/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 258 passed。
- 边界：每组至少 2 个有限值；Fligner-Wolfe 需要对照组，Mack-Wolfe 需要已知峰值组且只做单侧 greater；Chacko 只做 greater/less；秩/正态近似，Mack-Wolfe 有并列时精确方差不可用。

## 0.55.0 — 2026-10-31

- 新增：309 算子 / 82 Reader / 21 route；新增 Anscombe-Glynn 峰度、Bonett-Seier 峰度、Mauchly 球形三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension48.py` 4 项、`tests/test_r_oracles39.py` 1 项，合计 **5 passed**；Anscombe/Bonett 对照 R `moments`，Mauchly 对照 base R；registry clean；参考页 309/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 255 passed。
- 边界：Anscombe-Glynn 要求 n≥8，Bonett-Seier 要求 n≥3；Mauchly 要求 ≥3 特征、n>p、协方差非奇异且无缺失，使用卡方近似。

## 0.54.0 — 2026-10-31

- 新增：306 算子 / 82 Reader / 21 route；新增 Goldfeld-Quandt 异方差、Rainbow 线性偏离两个回归诊断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension47.py` 4 项、`tests/test_r_oracles38.py` 1 项，合计 **5 passed**；两个算子对照 R `lmtest::gqtest`、`lmtest::raintest`；registry clean；参考页 306/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 252 passed。
- 边界：两个算子都只支持单个响应 + 单个自变量 + 截距；Goldfeld-Quandt 的 `fraction` 为 [0,0.5)，Rainbow 的 `fraction` 为 (0,1)，中心子样本必须落在 [0,1] 内。

## 0.53.0 — 2026-10-31

- 新增：304 算子 / 82 Reader / 21 route；新增 Ansari-Bradley 秩尺度、χ² 方差离群、分箱校准曲线三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension46.py` 4 项、`tests/test_r_oracles37.py` 1 项，合计 **5 passed**；Ansari/χ² 离群对照 R `stats::ansari.test(exact=FALSE)`、`outliers::chisq.out.test`；registry clean；参考页 304/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 250 passed。
- 边界：Ansari 采用正态近似（含并列校正），不提供精确条件分布；χ² 离群要求方差为正、样本量至少 3；校准曲线要求二分类标签、概率在 [0,1]、每箱非空。

## 0.52.0 — 2026-10-31

- 新增：301 算子 / 82 Reader / 21 route；新增 D'Agostino 偏度、Pearson χ² 拟合优度、Cochran C 方差离群三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension45.py` 4 项、`tests/test_r_oracles36.py` 1 项，合计 **5 passed**；三算子分别对照 R `moments::agostino.test`、base R `chisq.test`、`outliers::cochran.test`；registry clean；参考页 301/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 247 passed。
- 边界：D'Agostino 要求 8–46340 个观测且方差非零；χ² 拟合优度要求计数非负、总计数为正，期望可为相对频数并归一化；Cochran C 要求每组至少两个有限值、组样本量相等、组方差为正。

## 0.51.0 — 2026-10-31

- 新增：298 算子 / 82 Reader / 21 route；新增 Fligner-Killeen 方差齐性、Mood 两样本尺度、Siegel-Tukey 秩离散度检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension44.py` 4 项、`tests/test_r_oracles35.py` 1 项，合计 **5 passed**；Fligner/Mood 对照 base R，Siegel-Tukey 对照 R `PMCMRplus::siegelTukeyTest`；registry clean；参考页 298/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 244 passed。
- 边界：Fligner-Killeen/Mood 要求每组至少两个有限值；Siegel-Tukey 不支持并列值，出现并列时明确报错，避免用近似 p 值冒充精确结果。

## 0.50.0 — 2026-10-31

- 新增：295 算子 / 82 Reader / 21 route；新增 Levene 方差齐性、Brown-Forsythe 稳健方差齐性、Barnard 精确独立性检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension43.py` 4 项、`tests/test_r_oracles34.py` 1 项，合计 **5 passed**；Levene/Brown-Forsythe 对照 R `DescTools::LeveneTest`，Barnard 对照 SciPy 1.17.1；registry clean；参考页 295/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 241 passed。
- 边界：Levene/Brown-Forsythe 要求至少两组、每组至少两个有限值；Barnard 要求 2×2 非负整数计数、边际非零，p 使用 SciPy 无条件精确算法。

## 0.49.0 — 2026-10-31

- 新增：292 算子 / 82 Reader / 21 route；新增 Durbin 平衡不完全区组检验、Skillings-Mack 缺失区组检验、Cuzick 有序趋势检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension42.py` 4 项、`tests/test_r_oracles33.py` 1 项，合计 **5 passed**；Durbin/Skillings-Mack/Cuzick 对照 R `PMCMRplus`；registry clean；参考页 292/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 238 passed。
- 边界：Durbin 要求平衡不完全区组、每块 k 个处理、每处理 r 次且 k<t；Skillings-Mack 允许缺失但要求共现图连通且协方差非奇异；Cuzick 默认得分 1..k，支持自定义有序得分、单双侧和连续性校正，不做并列校正。

## 0.48.0 — 2026-10-31

- 新增：289 算子 / 82 Reader / 21 route；新增 Conover 事后比较、Games-Howell 不等方差比较、Quade 区组秩检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension41.py` 4 项、`tests/test_r_oracles32.py` 1 项，合计 **5 passed**；Conover/Games-Howell/Quade 对照 R `DescTools`/`PMCMRplus`/`stats`；registry clean；参考页 289/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 235 passed。
- 边界：Conover 默认 Holm 校正，支持 bonferroni/BH/BY/none；Games-Howell 使用 Welch 自由度与 studentized range；Quade 要求完整随机区组、无缺失，区组内允许并列。

## 0.47.0 — 2026-10-31

- 新增：286 算子 / 82 Reader / 21 route；新增 Scheffe 事后比较、Nemenyi 事后比较、Pettitt 变点检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension40.py` 4 项、`tests/test_r_oracles31.py` 1 项，合计 **5 passed**；Scheffe/Nemenyi 对照 R `DescTools`，Pettitt 对照 R `trend`；registry clean；参考页 286/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 232 passed。
- 边界：Scheffe 使用 ANOVA 残差均方、F 分布和全族置信区间；Nemenyi 使用平均秩与 studentized range（df=Inf）；Pettitt 使用平均秩和渐近 p 值，并列最大变点全部记录。

## 0.46.0 — 2026-10-31

- 新增：283 算子 / 82 Reader / 21 route；新增 Sen 斜率、Mahalanobis 距离、Box's M 协方差齐性检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension39.py` 4 项、`tests/test_r_oracles30.py` 1 项，合计 **5 passed**；Sen 对照 SciPy `stats.theilslopes`，Mahalanobis 对照 R base，Box's M 对照 R `biotools::boxM`；registry clean；参考页 283/82；增量门 26 passed；`-W error` 7 passed；Studio 前端 229 passed。
- 边界：Sen 斜率至少 3 个完整对且 x 非常量；Mahalanobis 要求样本数大于特征数、协方差可逆、完整数值行；Box's M 要求每组样本数大于特征数、协方差可逆，使用卡方近似。

## 0.45.0 — 2026-10-31

- 新增：280 算子 / 82 Reader / 21 route；新增精确二项检验、Mood 中位数检验、Boschloo 精确检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension38.py` 4 项，合计 **4 passed**；权威实现为 SciPy 1.17.1（`stats.binomtest`、`stats.median_test`、`stats.boschloo_exact`）；registry clean；参考页 280/82；增量门 20 passed；`-W error` 6 passed；Studio 前端 226 passed。
- 边界：二项检验为单样本、CI 为 Clopper-Pearson；Mood 至少两组且每组有有限值、非常量，ties 支持 below/above/ignore；Boschloo 严格 2×2 非负整数，行列边际非零。

## 0.44.0 — 2026-10-31

- 新增：277 算子 / 82 Reader / 21 route；新增 Cox-Stuart 趋势检验、Grubbs 单离群值检验、Anderson-Darling 正态性检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension37.py` 5 项、`tests/test_r_oracles29.py` 1 项，合计 **6 passed**；R 对照 `randtests::cox.stuart.test`、`outliers::grubbs.test`、`nortest::ad.test`；registry clean；参考页 277/82；增量门 22 passed；`-W error` 8 passed；Studio 前端 223 passed。
- 边界：Cox-Stuart 奇数长度丢弃中间值、并列对剔除；Grubbs 只检验一个离群值；Anderson-Darling 要求 n>=8，使用估计参数与分段 p 近似。

## 0.43.0 — 2026-10-31

- 新增：274 算子 / 82 Reader / 21 route；新增 Page 有序备择检验、Mardia 多元正态性检验、Turning Point 序列随机性检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension36.py` 5 项、`tests/test_r_oracles28.py` 1 项，合计 **6 passed**；R 对照 `DescTools::PageTest`、`psych::mardia`、`randtests::turning.point.test`；registry clean；参考页 274/82；增量门 22 passed；`-W error` 8 passed；Studio 前端 220 passed。
- 边界：Page 仅完整区组、无并列值，小设计精确分布/大设计正态近似；Mardia 要求协方差可逆，给出两种偏度 p；Turning Point 不支持相邻并列值。

## 0.42.0 — 2026-10-31

- 新增：271 算子 / 82 Reader / 21 route；新增 Shapiro-Wilk 正态性检验、Lilliefors 正态性检验、Moses 极端反应检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension35.py` 4 项、`tests/test_r_oracles27.py` 1 项，合计 **5 passed**；R 对照 `stats::shapiro.test`、`DescTools::LillieTest`、`DescTools::MosesTest`；registry clean；参考页 271/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 217 passed。
- 边界：Shapiro-Wilk 使用 AS R94 近似、限制 3–5000 个样本；Lilliefors 使用 Dallal-Wilkinson p 近似；Moses 仅两组、精确组合 p，不提供置换/CI。

## 0.41.0 — 2026-10-31

- 新增：268 算子 / 82 Reader / 21 route；新增 Bhapkar 边际齐性检验、Von Neumann 随机性检验、Shapiro-Francia 正态性检验三个算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension34.py` 4 项、`tests/test_r_oracles26.py` 1 项，合计 **5 passed**；R 对照 `DescTools::BhapkarTest`、`DescTools::VonNeumannTest`、`DescTools::ShapiroFranciaTest`；registry clean；参考页 268/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 214 passed。
- 边界：Bhapkar 仅方表且要求正定协方差；Von Neumann 使用正态近似；Shapiro-Francia 使用正态化近似、仅 5–5000 个样本。

## 0.40.0 — 2026-10-31

- 新增：265 算子 / 82 Reader / 21 route；新增 Van der Waerden 正态得分检验、Bartels 秩检验、Woolf 同质 OR 检验三个非参数/随机性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension33.py` 4 项、`tests/test_r_oracles25.py` 1 项，合计 **5 passed**；R 对照 `DescTools::VanWaerdenTest`、`DescTools::BartelsRankTest`、`DescTools::WoolfTest`；registry clean；参考页 265/82；增量门 21 passed；Studio 前端 211 passed。
- 边界：Van der Waerden 仅两组；Bartels 要求 n>=10、使用正态近似；Woolf 零格自动 +0.5，不做三阶交互。

## 0.39.0 — 2026-10-31

- 新增：262 算子 / 82 Reader / 21 route；新增 Hotelling's T²、Yuen 截尾均值 t 检验、列联表 G 检验三个多元/稳健/分类数据检验算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension32.py` 4 项、`tests/test_r_oracles24.py` 1 项，合计 **5 passed**；R 对照 `DescTools::HotellingsT2Test`、`DescTools::YuenTTest`、`DescTools::GTest(correct="none")`；registry clean；参考页 262/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 208 passed。
- 边界：Hotelling T² 使用合并协方差与 F 近似；Yuen 使用 `trim=0.2` 默认与 Welch 自由度，不提供 exact p；G-test 不做 Yates/Williams 校正。

## 0.38.0 — 2026-10-31

- 新增：259 算子 / 82 Reader / 21 route；新增 Somers' D、Goodman-Kruskal gamma、Kendall's W 三个有序关联/一致性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension31.py` 4 项、`tests/test_r_oracles23.py` 1 项，合计 **5 passed**；R 对照 `DescTools::SomersDelta`、`DescTools::GoodmanKruskalGamma`、`DescTools::KendallW(correct=FALSE)`；registry clean；参考页 259/82；增量门 21 passed；Studio 前端 205 passed。
- 边界：Somers' D 需选择 `direction`；gamma 不提供 CI；Kendall's W 使用列排名与 `correct=FALSE` 语义，不做并列秩校正/事后两两比较。

## 0.37.0 — 2026-10-31

- 新增：256 算子 / 82 Reader / 21 route；新增 Cramér's V、Jonckheere-Terpstra 有序秩检验、varimax 正交旋转三个效应量/多变量算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension30.py` 4 项、`tests/test_r_oracles22.py` 1 项，合计 **5 passed**；R 对照 `DescTools::CramerV`、`DescTools::JonckheereTerpstraTest(exact=FALSE)`、`stats::varimax`；registry clean；参考页 256/82；增量门 33 passed；Studio 前端 202 passed。
- 边界：Cramér's V 仅二维列联表；Jonckheere-Terpstra 使用正态近似，不提供 exact p；varimax 仅正交旋转，不做斜交旋转/因子数选择。

## 0.36.0 — 2026-10-31

- 新增：253 算子 / 82 Reader / 21 route；新增 KMO 取样适切性、Bartlett 球形检验两个因子可分析性诊断算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension29.py` 3 项、`tests/test_r_oracles21.py` 1 项，合计 **4 passed**；R 对照 `psych::KMO`、`psych::cortest.bartlett`；registry clean；参考页 253/82；增量门 20 passed；`-W error` 6 passed；Studio 前端 199 passed。
- 边界：KMO 要求完整样本、非奇异相关矩阵；Bartlett 要求正定相关矩阵；不做因子数选择或旋转。

## 0.35.0 — 2026-10-31

- 新增：251 算子 / 82 Reader / 21 route；新增 Cronbach's alpha、典型相关、Wald–Wolfowitz runs test 三个可靠性/多变量算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension28.py` 4 项、`tests/test_r_oracles20.py` 1 项，合计 **5 passed**；R 对照 `psych::alpha`、`stats::cancor`、`randtests::runs.test`；registry clean；参考页 251/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 197 passed。
- 边界：alpha 使用完整样本与样本方差；canonical 使用 QR+SVD 且只输出相关系数/平方；runs 默认中位数、丢弃并列值、正态近似。

## 0.34.0 — 2026-10-31

- 新增：248 算子 / 82 Reader / 21 route；新增配对 ROC 比较（DeLong）与 Cochran Q 两个配对/匹配检验算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension27.py` 3 项、`tests/test_r_oracles19.py` 1 项，合计 **4 passed**；R 对照 `pROC::roc.test(method="delong")`、`DescTools::CochranQTest`；registry clean；参考页 248/82；增量门 20 passed；`-W error` 6 passed；Studio 前端 194 passed。
- 边界：`roc_comparison` 要求同一样本、较高分数为阳性，不自动翻转方向；`cochran_q` 仅接受宽表二分类完整样本，不做事后两两比较。

## 0.33.0 — 2026-10-31

- 新增：246 算子 / 82 Reader / 21 route；新增 Passing-Bablok 与 Deming 回归两个方法学一致性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension26.py` 3 项、`tests/test_r_oracles18.py` 1 项，合计 **4 passed**；R 对照 `mcr::mcreg`；registry clean；参考页 246/82；增量门 20 passed；`-W error` 6 passed；Studio 前端 192 passed。
- 边界：仅输出斜率/截距点估计，不输出 CI；Passing-Bablok 拒绝负值，Deming 要求正 `error_ratio` 与非零协方差；不做加权或重复测量模型。

## 0.32.0 — 2026-10-31

- 新增：244 算子 / 82 Reader / 21 route；新增 ICC（组内相关）、Lin's CCC（一致性相关系数）两个可靠性算子；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension25.py` 4 项、`tests/test_r_oracles17.py` 1 项，合计 **5 passed**；R 对照 `irr::icc`、`DescTools::CCC`；registry clean；参考页 244/82；增量门 21 passed；`-W error` 7 passed；Studio 前端 190 passed。
- 边界：ICC 的 r0 固定为 0；CCC 使用 z-transform CI；两者均不做缺失插补。

## 0.31.0 — 2026-10-31
- 新增 2 个回归模型算子：`gamma_regression`（Gamma GLM，log link）、`zero_inflated_poisson`（零膨胀 Poisson）；未新增 Reader。
- 恢复并保留 0.15 既有 `quantile_regression`（ML 算子）；本批不重复注册同名算子。
- 当前：242 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension24.py` 3 项、`tests/test_r_oracles16.py` 1 项，合计 **4 passed**；R 对照 base `glm(Gamma, log)`、`pscl::zeroinfl`；registry clean；参考页 242/82；增量门 20 passed；Studio 前端 188 passed。
- 边界：Gamma 使用 log link 与 MLE 尺度；零膨胀 Poisson 零模型默认仅截距，可选 `zero_predictors`；不提供稳健标准误或随机效应。

## 0.30.0 — 2026-10-31
- 新增 3 个回归模型算子：`multinomial_logit`（多项 logit）、`conditional_logit`（条件 logit）、`robust_regression`（Huber M 稳健回归）；未新增 Reader。
- 当前：240 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension23.py` 4 项、`tests/test_r_oracles15.py` 1 项，合计 **5 passed**；R 对照 `nnet::multinom`、`survival::clogit`、`MASS::rlm(psi=psi.huber)`；registry clean；参考页 240/82；增量门 21 passed；Studio 前端 186 passed。
- 边界：多项 logit 使用第一水平为 reference；条件 logit 按 stratum 匹配；稳健回归使用 Huber M 估计，不提供 MM/自适应估计或稳健标准误。

## 0.29.0 — 2026-10-31
- 新增 3 个回归诊断算子：`breusch_godfrey`（Breusch-Godfrey 序列相关）、`reset_test`（RESET 函数形式）、`harvey_collier`（Harvey-Collier 线性性）；未新增 Reader。
- 当前：237 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension22.py` 4 项、`tests/test_r_oracles14.py` 1 项，合计 **5 passed**；R 对照 `lmtest`；registry clean；参考页 237/82；增量门 22 passed；Studio 前端 183 passed。
- 边界：BG 为 LM/F 渐近检验；RESET 使用拟合值幂次增广；Harvey-Collier 使用递归残差；均不替代稳健标准误或因果识别。

## 0.28.0 — 2026-10-31
- 新增 3 个算子：`granger_causality`（Granger 因果 F 检验）、`arch_test`（ARCH LM 检验）、`flow_compensate`（流式溢漏补偿）；未新增 Reader。
- 当前：234 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension21.py` 4 项、`tests/test_r_oracles13.py` 1 项，合计 **5 passed**；R 对照 `lmtest`、`FinTS`、`flowCore`；registry clean；参考页 234/82；增量门 22 passed；Studio 前端 180 passed。
- 边界：Granger 为双变量 F 检验；ARCH 使用平方序列 LM；flow_compensate 只处理方阵线性溢漏补偿。

## 0.27.0 — 2026-10-31
- 新增 4 个统计算子：`adf_test`（ADF 单位根）、`kpss_test`（KPSS 平稳性）、`poisson_regression`（Poisson GLM）、`negative_binomial_regression`（NB2 回归）。
- 当前：231 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension20.py` 5 项、`tests/test_r_oracles12.py` 1 项，合计 **6 passed**；R 对照 `tseries`、base `glm`、`MASS::glm.nb`；registry clean；参考页 231/82；增量门 22 passed；Studio 前端 177 passed。
- 边界：ADF 默认含常数和线性趋势，R p 表与 statsmodels 查表在边界处不同；KPSS p 超出表范围时截断为 0.1；Poisson/NB 回归输出 rate ratio；NB 标准误使用 statsmodels 信息矩阵。

## 0.26.0 — 2026-10-31
- 新增 2 个流式细胞术算子：`flow_transform`（arcsinh 变换，兼容 `flowCore::arcsinhTransform`）和 `flow_gate`（二维矩形门控，闭区间）。
- 当前：227 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension19.py` 4 项、`tests/test_r_oracles11.py` 1 项，合计 **5 passed**；R 对照 `flowCore`；registry clean；参考页 227/82；增量门 21 passed；Studio 前端 173 passed。
- 边界：只处理 FCS 事件矩阵的二维轴对齐门；不实现多边形/布尔门，不展开原始峰列表。

## 0.25.0 — 2026-10-31
- 新增 3 个回归/时间序列诊断算子：`white_test`（White 异方差）、`chow_test`（Chow 结构突变）、`ljung_box`（Ljung-Box 自相关）。
- 当前：225 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension18.py` 5 项、`tests/test_r_oracles10.py` 1 项，合计 **6 passed**；R 对照 base `lm` 与 `Box.test`；registry clean；参考页 225/82；增量门 22 passed；Studio 前端 171 passed。
- 边界：White 使用含平方项和交叉项的辅助回归；Chow 按样本行顺序在 `break_fraction` 处分段；Ljung-Box 为原始序列（去均值）而非回归残差。

## 0.24.0 — 2026-10-31
- 新增 3 个临床预测评估算子：校准截距/斜率、连续 NRI、IDI。
- 当前：222 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension17.py` 4 项、`tests/test_r_oracles9.py` 1 项，新增 **5 passed**；R 对照 base `glm` 与公式；registry clean；参考页 222/82；增量门 21 passed；Studio 前端 168 passed。
- 边界：校准截距用 offset 模型；NRI 为连续 NRI（不含分类切点）；IDI 为二分类判别斜率差。

## 0.23.0 — 2026-10-31
- 新增 3 个生存预测算子：时间依赖 AUC、Brier 分数、积分 Brier 分数。
- 当前：219 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension16.py` 4 项、`tests/test_r_oracles8.py` 1 项，新增 **5 passed**；R 对照 `survivalROC`、`survival::coxph`、`survival::brier`；registry clean；参考页 219/82；增量门 21 passed；Studio 前端 165 passed。
- 文档：新增 `docs/vision.md`（价值主张与设计原则），README、架构、AGENTS、LLM/用户指南同步定位。
- 边界：时间依赖 AUC 只实现 KM 法；Brier 使用 Cox PH 的 IPCW 与 R timefix；积分 Brier 只对给定 times 做梯形积分。

## 0.22.0 — 2026-10-31
- 新增 2 个 Reader：FCS 流式细胞术事件矩阵、AB1 Sanger 测序 basecall/trace。
- 当前：216 算子 / 82 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension15_readers.py` 7 项、`tests/test_r_oracles7.py` 1 项，新增 **8 passed**；增量门 **24 passed**，`-W error` 下 **10 passed**；R 对照 flowCore 2.14.2 / sangerseqR 1.38.0；registry clean；参考页 216/82；Studio 前端 162 passed。
- 依赖：cytolib/flowCore 用 BH 1.84 用户库编译；sangerseqR 从 Bioconductor 安装。
- 边界：FCS 支持 list mode 与 I/F/D 数据，AB1 只解析常用 ABIF tag；不重做 basecalling、不展开原始峰列表。

## 0.21.0 — 2026-10-31
- 新增 8 个算子：Storey q-value、DeLong AUC、Dunn 检验、决策曲线、有序 logistic、线性混合模型、Hosmer-Lemeshow、Stuart-Maxwell。
- 当前：216 算子 / 80 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension14.py` 8 项、`tests/test_r_oracles6.py` 2 项，新增 **10 passed**；增量门 **26 passed**，`-W error` 下 **12 passed**；R 对照 pROC/dunn.test/dcurves/MASS/lme4/ResourceSelection/DescTools；registry clean；参考页 216/80；Studio 前端 **162 passed**。
- 未新增 Reader：`flowCore` 因 `cytolib` 编译失败、`sangerseqR` 未安装，FCS/AB1 暂缓。
- 边界：Storey 固定 lambda；DeLong 正态近似；Dunn 标准 Holm；决策曲线 0.01–0.99；有序 logistic/logit-probit；LMM 随机截距；HL 唯一分位数切点；Stuart-Maxwell 移除等边际类别。

## 0.20.0 — 2026-10-31
- 新增 8 个算子：Cohen's kappa、Fleiss' kappa、Breusch-Pagan、Durbin-Watson、Egger 回归检验、ANOSIM、Procrustes、偏 Mantel。
- 新增 4 个 Reader：mzIdentML、pepXML、mzDATA、protXML；MGF 空峰谱修复沿用 0.19。
- 当前：208 算子 / 80 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension13.py` 6 项、`tests/test_extension13_readers.py` 5 项、`tests/test_r_oracles5.py` 1 项，新增 **12 passed**；R 对照 vegan/lm，Python 对照 statsmodels；registry clean；参考页 208/80；增量门 **28 passed**，`-W error` 下 **14 passed**；Studio 前端 **154 passed**。
- 边界：kappa 支持无权重/线性/二次；Fleiss 支持 fleiss/randolph；ANOSIM/Procrustes/偏 Mantel 采用 vegan 语义；质谱 Reader 只输出摘要字段，不展开原始峰。

## 0.19.0 — 2026-10-30
- 新增 7 个算子：TMM 归一化、limma 风格批次效应移除、Mantel-Haenszel、Cochran-Armitage 趋势、TOST 等价检验、Bland-Altman、竞争风险累积发生率。
- 新增 3 个 Reader：mzML、mzXML、mzTab；修复 MGF 空峰谱 precursor 丢失。
- 当前：200 算子 / 76 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量，`tests/test_extension12.py` 7 项、`tests/test_extension12_readers.py` 4 项、`tests/test_r_oracles4.py` 6 项，新增 **17 passed**；增量门 **42 passed**；R 对照 edgeR/limma/mantelhaen.test/prop.trend.test/t.test/survfit；registry clean；参考页 200/76；Studio 前端 **146 passed**。
- 边界：TMM 采用 edgeR 的 f75 参考与 trimmed weighted mean；批次校正采用 sum-to-zero 编码；Mantel-Haenszel 默认不做连续性校正；Cochran-Armitage 使用等距 scores；TOST 支持 Welch/pooled；Bland-Altman 使用正态近似 LoA；CIF 为 Aalen-Johansen，事件 0/1/2；mzML/mzXML/mzTab 只输出摘要，不展开原始峰列表。

## 0.18.0 — 2026-10-30
- 新增 14 个算子：反向互补、翻译、密码子使用、限制性酶切位点、蛋白性质；PCA loadings、HVG、细胞周期评分、Hudson Fst、GRM 亲缘矩阵、RMST、peptide q-value、McNemar、Kendall tau。
- 新增 10 个 Reader：FAM、BIM、HapMap、MOL、XYZ、GRO、PSL、genePred、MGF、HMMER domtbl。
- 当前：193 算子 / 73 Reader / 21 route；未修改核心层。
- 验证：增量 `tests/test_extension11.py` 9 项 + R `cor.test(kendall)` oracle 6 项全部通过；全量 pytest **606 passed / 1 skipped**（唯一 skip 为增量门 full-suite 模式分支）；registry clean；参考页 193/73；Studio 前端 **139 passed**，构建通过。
- 边界：翻译使用标准遗传密码、不支持线粒体/非标准密码表；限制性酶切位点只做精确 motif 计数；蛋白 pI/MW 为常用近似；HVG 基于均值-离散度；Fst 使用 Hudson 估计；RMST 需组列且基于 KM；peptide q-value 使用 target-decoy；McNemar 默认连续性校正；Kendall 为成对完整观测；HapMap 以首个非缺失等位基因为参考；MOL2/PDB 不重建键级；PSL/genePred 只解析常用字段。

BioPipe 使用语义化版本和 git tag。当前源码版本：**0.49.0（2026-10-31）**。
更早版本从 git tag/history 查；本页只保留当前版本摘要。

## 0.17.0 — 2026-10-30
- 新增 12 个算子：Holm、Benjamini-Yekutieli、Cohen's d/Hedges g、Cliff's delta、η²、rank-biserial、Davies-Bouldin、Calinski-Harabasz、ARI、混淆矩阵、ROC 曲线、Mann-Kendall。
- 新增 8 个 Reader：BLAST tabular、HMMER tblout、InterProScan、EMBL、HMM、MOL2、SMI、bedMethyl。
- 当前：179 算子 / 63 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑增量 **11 passed**（`tests/test_extension10.py` 10 项 + R `p.adjust` oracle 1 项），未重跑全量；registry clean；参考页 179/63；Studio 前端 **125 passed**。
- 边界：Holm/BY 对 NaN p 保留 NaN；效应量只支持连续特征；Mann-Kendall 使用 tie-corrected 正态近似；聚类标签编号不稳定；SMI 的重原子计数为近似值；MOL2 不重建键级；bedMethyl 仅解析 15 列常用字段。

## 0.16.0 — 2026-10-30
- 新增 9 个算子：DBSCAN、层次聚类、GMM、孤立森林、Cramér–von Mises、Welch ANOVA、Tukey HSD、C-index、二分类指标。
- 新增 6 个 Reader：WIG、broadPeak、GFF2、mmCIF、OBO、SDF。
- 当前：167 算子 / 55 Reader / 21 route；未修改核心层。
- 验证：按用户要求只跑 **增量测试 12 passed**（`tests/test_extension9.py`），未重跑全量；registry clean；参考页 167/55；Studio 前端 **113 passed**。
- 边界：聚类标签不稳定；Cramér–von Mises 仅两组；Welch ANOVA/Tukey HSD 至少三组；C-index 的 risk 越高表示风险越大；分类指标仅二分类；GFF Reader 使用 `.gff2` 避免与 Gff3Reader 冲突；WIG/broadPeak 0-based；mmCIF 仅 atom_site；OBO 仅 Term；SDF 不重建键图。

## 0.15.0 — 2026-10-30
- 新增 6 个算子：Mantel 检验、PLS 回归、分位数回归、bootstrap 置信区间、silhouette、互信息。
- 新增 4 个 Reader：GenBank、PDB、Zarr、BCF。
- 当前：158 算子 / 49 Reader / 21 route；未修改核心层。
- 验证：**560 passed / 0 skipped**（2026-10-30）；registry clean；参考页 158/49；新增测试 `tests/test_extension8.py` 8 项；Studio 前端 **104 passed**。
- 边界：Mantel 使用 Pearson 相关 + 置换，p 的分辨率为 `1/(n_perm+1)`；PLS 对单目标暴露一维 `coef_` 适配器；分位数回归使用 sklearn `QuantileRegressor`（无 `max_iter`）；bootstrap 为 percentile CI；GenBank/PDB 为常用子集解析；Zarr 只接受 2D 数值数组；BCF 需 pysam，原生 Windows 不可用（见 [Windows 兼容性](windows_compatibility.md)）。

## 0.14.0 — 2026-10-30
- 新增 8 个算子和 5 个 Reader：距离相关、偏相关、VIF、分位数/幂变换、稳健缩放、缩尾、秩变换；BAM、CRAM、BigWig、PED、GFA。
- 当前：152 算子 / 45 Reader / 21 route；未修改核心层。
- 验证：**552 passed / 0 skipped**（2026-10-30）；registry clean；参考页 152/45；新增测试 `tests/test_extension7.py` 8 项；Studio 前端 **98 passed**。
- 边界：BAM/CRAM 只暴露常用字段；CRAM 必须提供 reference；PED dosage 不含参考等位基因；BigWig 只读取区间值；GFA 只读取 S 段；距离相关不提供 p 值；VIF 对完全共线特征返回 inf。

## 0.13.0 — 2026-10-30
- 新增 6 个统计算子：KS 两样本、Brunner-Munzel、Fligner-Killeen、置换检验、符号检验、Jarque-Bera。
- 当前：144 算子 / 40 Reader / 21 route；未修改核心层。
- 验证：**544 passed / 0 skipped**（2026-10-30）；registry clean；参考页 144/40；新增测试 `tests/test_extension6.py` 4 项；Studio 前端 **90 passed**。
- 边界：K-S/置换检验的 p 值基于有限重采样或渐近近似；Fligner-Killeen 依赖 scipy 当前版本 API。

## 0.12.0 — 2026-10-30
- 新增 6 个算子：UMAP、配对 t 检验、单样本 t 检验、z-score、min-max 缩放、softmax。
- 新增 2 个 Reader：MAF、UCSC chain。
- 当前：138 算子 / 40 Reader / 21 route；未修改核心层。
- 验证：**540 passed / 0 skipped**（2026-10-30）；registry clean；参考页 138/40；新增测试 `tests/test_extension5.py` 6 项；Studio 前端 **84 passed**。
- 边界：UMAP 依赖 umap-learn；z-score 是 axis-wise 便捷算子，与既有 `scale_features` 有功能重叠；MAF/chain 只校验固定列/头，不验证完整规范。

## 0.11.0 — 2026-10-30
- 新增 10 个算子：谱嵌入、LLE、Gaussian 随机投影、主题 LDA、Wilcoxon、Friedman、Bartlett、Normaltest、Bonferroni、Fisher 合并 p 值。
- 新增 6 个 Reader：PAF、SAM、BEDPE、cytoband、Clustal、NEXUS。
- 当前：132 算子 / 38 Reader / 21 route；未修改核心层，扩展仍通过声明和生成式 registry 完成。
- 验证：**534 passed / 0 skipped**（2026-10-30）；registry clean；参考页 132/38；新增测试 `tests/test_extension4.py` 9 项；Studio 前端 **78 passed**。

## 0.10.0 — 2026-10-29
- 新增 31 个算子：线性/弹性网/贝叶斯岭/Huber/Theil-Sen 回归，Kernel PCA、Truncated SVD、因子分析、MDS、Isomap、BH FDR、Mann-Whitney，以及 11 个树模型/朴素贝叶斯/判别分析/随机梯度模型。
- 新增 13 个 Reader：Excel、GCT、bedGraph、narrowPeak、NumPy、JSON 表、FAI、FASTQ、HDF5、PLINK MAP、PHYLIP、Newick、Stockholm。
- 当前：122 算子 / 32 Reader / 21 route；全部严格 schema/contracts；未修改核心层。
- 验证：**525 passed / 0 skipped**（2026-10-29）；参考页生成检查；registry clean；新增算子/Reader 测试 31 个，Excel/HDF5/Newick 等边界单独覆盖。

## 0.9.0 — 2026-10-29

**主题：批次校正与 ssGSEA。**

- 新增算子 `combat`：基于 Scanpy 的 ComBat，另有 `mean_center` 轻量模式；适配 metadata 批次列和 sample 轴。
- 新增算子 `ssgsea`：按 GSVA `ssgsea` 的 rank-sum 路径实现；输出 sample × gene-set 分数。
- 新增 route：`single_cell_batch`（单细胞去批次 + marker score）、`rnaseq_ssgsea`（RNA-seq ssGSEA）。
- 当前：91 算子 / 19 Reader / 21 route；全部严格 schema/contracts。
- 验证：**494 passed / 0 skipped**（2026-10-29）；21/21 route 用仓库 fixture 实际执行；`ssgsea` 与 R GSVA 1.28 对拍；参考页生成检查；Studio 前端 **68 passed**；R oracle **7 passed**。
- 边界：`combat` 未与 R `sva::ComBat` 做独立数值对拍；`ssgsea` 只覆盖 GSVA 的 rank-sum 变体。

## 0.8.0 — 2026-10-27

**主题：第一批按路径热度扩展 Reader、算子和 route。**

- 新增 3 个 Reader：`GmtReader`（GMT 基因集）、`LoomReader`（Loom 单细胞）、`BiomReader`（BIOM JSON/HDF5）。
- 新增 11 个算子：`gsea`、`ora`、`doublet_detect`、`pseudobulk`、`marker_score`、`meta_analysis`、`prs`、`protein_rollup`、`limma_de`、`ancom_bc`、`aldex2`。
- 新增 5 条 route：`rnaseq_de_enrichment`、`single_cell_loom`、`gwas_meta_prs`、`proteomics_limma`、`microbiome_diff`。
- 当前：89 算子 / 19 Reader / 19 route；全部严格 schema/contracts。
- 全 route fixture 验证：19 条 route 均在 pytest 内实际执行；Multi-omics 相关矩阵前增加方差 top-500 预筛选。
- 新增 Reader/算子/route 单测与端到端 smoke test；`doublet_detect`/`marker_score` 直接调用 Scanpy，`aldex2`/`ancom_bc` 为独立 log-ratio 实现并在文档中明确边界。
- 验证：**488 passed / 0 skipped**（2026-10-29）；19/19 route 用仓库 fixture 实际执行；参考页生成检查；Studio 新算子展示补齐，前端 **66 passed**；新增 `tests/test_r_oracles.py` 6 个 R 4.3.3/Bioc 3.18 对拍（limma 普通 t、fgsea ES、metafor FE/DL、phyper、独立 log-ratio/Welch），全部通过；`limma_de` 默认 eBayes 先验、`ancom_bc`/`aldex2` 完整 R 包行为仍未对拍。

## 0.7.0 — 2026-10-27

**主题：严格契约、Agent/SOP 文档、Studio 导入修复。**

- 16 个 Reader / 78 个算子全部严格 schema（`additionalProperties: false`）；30 个 legacy 算子迁移到源码声明，`operator_ui.json` 只保留展示元数据。
- Reader/算子参数补齐 title、basic/advanced 分组、单位；`Step`/`Reader` 基类强制严格校验。
- 新增 78 个算子页、16 个 Reader 页、机器索引、SOP/LLM/用户手册、ANALYSIS 模板和路线架构师提示词。
- 新增 `biopipe inspect` 与 `scripts/run.py tasks/<dir> --check`。
- 修复 Studio 导入：从 `code_root` 搜索任务输入；支持 YAML 绝对路径；跨盘 job 不再调用 `os.path.relpath`；重选文件保留 Reader 参数；`_input_names` 在边界剥离。
- heatmap 增加 `max_cells`/`max_pixels`，阻止 5247×5247 相关矩阵触发 168 GiB 渲染分配。
- 验证：440 passed / 12 skipped、14/14 verify、49/49 demo、registry check、ruff、compileall、portability。
- Windows 环境快照：[conda](../windows-biopipe-conda.yml) / [pip](../windows-biopipe-pip-freeze.txt)。

## 更早版本

| 版本 | 说明 |
|---|---|
| 0.4.1 | 已发布的 Windows 桌面版；64 算子、15 Reader、5 路线 |
| 0.3.x | 上游引擎/桌面迭代 |
| 0.2.x | 早期桌面与协议 |

历史发布说明不单独维护；需要追溯时从 git tag/release history 查看。
