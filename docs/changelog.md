# 更新记录

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
