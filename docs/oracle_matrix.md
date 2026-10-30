# 权威实现对照矩阵

本页记录扩展算子与外部权威实现的对标方式。原则：优先使用同语义的成熟实现；数值差异必须能由算法差异、参数或浮点精度解释；不能对标的项要明确写出原因。

## 0.20.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cohens_kappa` | Python `statsmodels.stats.inter_rater.cohens_kappa` | `tests/test_extension13.py` | 无权重/线性/二次权重；统计量与 p 值同源 |
| `fleiss_kappa` | Python `statsmodels.stats.inter_rater.fleiss_kappa` | `tests/test_extension13.py` | `fleiss`/`randolph` 两种方法 |
| `breusch_pagan` | Python `statsmodels.stats.diagnostic.het_breuschpagan` | `tests/test_extension13.py` | 对 float32 输入允许 `rel=1e-5` 的浮点误差 |
| `durbin_watson` | Python `statsmodels.stats.stattools.durbin_watson` | `tests/test_extension13.py` | 残差顺序按输入行顺序 |
| `egger_test` | R `lm(effect/se ~ 1/se)` | `tests/test_r_oracles5.py` | 未加权 OLS；截距、斜率、t、p 对齐 |
| `anosim` | R `vegan::anosim` | `tests/test_r_oracles5.py` | 秩和置换；`R` 与 R 一致 |
| `procrustes` | R `vegan::procrustes(scale=TRUE, symmetric=FALSE)` | `tests/test_r_oracles5.py` | 对齐 `ss`、`scale` 和由 `ss` 推出的 `r`；不做反射 |
| `partial_mantel` | R `vegan::mantel.partial` | `tests/test_r_oracles5.py` | 对距离下三角残差化；`r=0.923474` 对齐 |

关键数值（测试 fixture）：

- Egger：截距 `1.883214`，斜率 `0.0166146`，截距 p `0.487185`。
- ANOSIM：`R=1`。
- Procrustes：`ss=7.105427e-15`，`scale=1`，由 R `ss` 推出 `r≈1`。
- Partial Mantel：`r=0.923474`。

## 0.21.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `storey_qvalue` | R `p.adjust(BH)` + 固定 lambda pi0 公式 | `tests/test_r_oracles6.py` | qvalue 包当前版本不接受 `pi0.method="fixed"`，用等价固定 pi0/BH 公式；pi0 与 q 值对齐 |
| `delong_auc` | R `pROC::roc` + `ci.auc(method="delong")` | `tests/test_r_oracles6.py` | AUC、DeLong CI 对齐 |
| `dunn_test` | R `dunn.test::dunn.test` | `tests/test_r_oracles6.py` | 原始 z/P 对齐；算子用标准 Holm，R 的 P.adjust 非单调，差异已记录 |
| `decision_curve` | R `dcurves::dca` | `tests/test_r_oracles6.py` | 阈值 0.2/0.4/0.6 的 net benefit 对齐 |
| `ordinal_logistic` | R `MASS::polr` | `tests/test_r_oracles6.py` | 去掉 intercept 后系数、阈值、logLik 对齐 |
| `linear_mixed_model` | R `lme4::lmer` + `VarCorr` | `tests/test_r_oracles6.py` | 固定效应、组间/残差方差对齐 |
| `hosmer_lemeshow` | R `ResourceSelection::hoslem.test` | `tests/test_r_oracles6.py` | 唯一分位数切点；统计量/df/p 对齐 |
| `stuart_maxwell` | R `DescTools::StuartMaxwellTest` | `tests/test_r_oracles6.py` | 2 个 rater、4 类；统计量/df/p 对齐 |

- 本轮新增 R 包：`pROC`、`dunn.test`、`dcurves`、`ResourceSelection`、`DescTools`；已有 `MASS`、`lme4`。
- 尝试的 Reader 依赖：`flowCore` 因 `cytolib` 编译失败；`sangerseqR` 未安装。因此 0.21 不新增 Reader，FCS/AB1 延后。
- Python 侧仍使用 `statsmodels 0.14.6`、`scipy 1.17.1`；未依赖未安装的 PyPI 包。
- 复现：`python -m pytest -q tests/test_extension14.py tests/test_r_oracles6.py`。

## 0.22.0

| Reader | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `FcsReader` | R `flowCore::read.FCS(transformation=FALSE)` | `tests/test_r_oracles7.py` | 10000×8 事件/通道、前两行、通道名完全一致；fixture 为 FACSCalibur FCS 2.0 |
| `Ab1Reader` | R `sangerseqR::read.abif` | `tests/test_r_oracles7.py` | PBAS 序列、PCON 前 10、PLOC 前 10、FWO 通道顺序一致 |

- 本轮修复依赖：`cytolib` 2.14.1 与 BH 1.90 的 `boost::filesystem` 私有 API 冲突；安装 BH 1.84.0.0 到用户库后编译 `cytolib`/`flowCore`，再复制到主库。
- 当前 R：`flowCore 2.14.2`、`sangerseqR 1.38.0`；已安装 `BH 1.84.0.0` 于 `<R 用户库>/boost184`。
- 未安装 `ShortRead`；FCS/AB1 已不再属于缺口。

## 0.23.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `time_dependent_auc` | R `survivalROC::survivalROC(method="KM")` | `tests/test_r_oracles8.py` | AUC@5/10/15 完全一致；仅 KM 法 |
| `brier_score` | R `survival::brier` + `coxph` | `tests/test_r_oracles8.py` | 三点 Brier 一致；含删失 timefix |
| `integrated_brier_score` | 上述 Brier 的梯形积分 | `tests/test_r_oracles8.py` | IBS 1.7687351192 一致 |

- 新增/使用的 R 包：`survivalROC 1.0.3.1`、`survival 3.5.8`；已有 `survival`/`survivalROC`。
- R 参考值：AUC@5/10/15 = 0.6552020987/0.8091230111/0.6519226986；Brier = 0.1315697618/0.1807035261/0.2145172338；IBS = 1.7687351192。
- 复现：`python -m pytest -q tests/test_extension16.py tests/test_r_oracles8.py`。

## 0.24.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `calibration_slope` | R base `glm`（offset 截距 + lp 斜率） | `tests/test_r_oracles9.py` | 截距/斜率/SE 一致 |
| `net_reclassification_improvement` | R base 连续 NRI 公式 | `tests/test_r_oracles9.py` | NRI 1.0 一致 |
| `integrated_discrimination_improvement` | R base IDI 公式 | `tests/test_r_oracles9.py` | IDI 0.1083333 一致 |

- 本轮不新增 R 包；使用 base `stats::glm`、`qlogis`。
- 参考值：截距 -0.4063779、斜率 3.621762、斜率 SE 2.577094；NRI 1.0；IDI 0.1083333。
- 复现：`python -m pytest -q tests/test_extension17.py tests/test_r_oracles9.py`。

## 0.25.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `white_test` | R base `lm` 辅助回归（平方项/交叉项） | `tests/test_r_oracles10.py` | LM/F 与 R 一致；辅助回归 5 个自由度 |
| `chow_test` | R base `lm` + F 检验 | `tests/test_r_oracles10.py` | F/RSS 一致；按行顺序分段 |
| `ljung_box` | R base `Box.test(type="Ljung-Box")` | `tests/test_r_oracles10.py` | Q/p 一致；原始序列去均值 |

- 本轮不新增 R 包；使用 base `stats::lm` 与 `stats::Box.test`。
- 参考值：White LM 5.6138306138、p 0.3456253123、F 1.0926275992；Chow F 25.2160566352、p 1.13223e-05；Ljung-Box Q 37.7313478225、p 4.272e-07。
- 复现：`python -m pytest -q tests/test_extension18.py tests/test_r_oracles10.py`。

## 0.26.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `flow_transform` | R `flowCore::arcsinhTransform(a=0,b=1,c=5)` + `transform` | `tests/test_r_oracles11.py` | 前两行 FSC-H/FL1-H 完全一致；未选通道不变 |
| `flow_gate` | R `flowCore::rectangleGate` + `filter` | `tests/test_r_oracles11.py` | FSC-H 100..500、SSC-H 50..400：6959/10000，比例 0.6959 |

- 本轮使用已安装的 `flowCore 2.14.2`，无需新增 R 包。
- 参考值：变换 `[11.6385695024, 12.1196362926]`、`[12.1356879809, 11.1944095560]`；门控 `6959/10000`、`p=0.6959`。
- 边界：arcsinh 公式为 `asinh(a + b*x) + c`；矩形门控为闭区间、仅二维轴对齐；不实现多边形/布尔门。
- 复现：`python -m pytest -q tests/test_extension19.py tests/test_r_oracles11.py`。


## 0.27.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `adf_test` | R `tseries::adf.test(x, k=2)` | `tests/test_r_oracles12.py` | 统计量、lag 对齐；R p 表更粗，边界 p 记录差异 |
| `kpss_test` | R `tseries::kpss.test(x, null="Level", lshort=TRUE)` | `tests/test_r_oracles12.py` | 统计量、lags 对齐；p 超出表范围时截断 0.1 |
| `poisson_regression` | R base `glm(y ~ x, family=poisson)` | `tests/test_r_oracles12.py` | 系数、标准误、rate ratio 对齐 |
| `negative_binomial_regression` | R `MASS::glm.nb(y ~ x)` | `tests/test_r_oracles12.py` | 系数、alpha/theta 对齐；标准误因信息矩阵略有差异 |

- 新增 R 包 `tseries 0.10-63`（含 xts/TTR/quadprog/quantmod）；使用 base `glm` 与 `MASS`。
- 关键值：ADF 统计量 `-3.3953961017`；KPSS `0.1696735045`、lags 3；Poisson 系数 `0.8213881/1.0349290`；NB 系数 `0.8028424/1.1345920`、theta `2.261968`。
- 复现：`python -m pytest -q tests/test_extension20.py tests/test_r_oracles12.py`。
- 边界：ADF 默认 `regression="ct"`；KPSS 的 `lags` 可固定；Poisson/NB 响应必须为非负计数；NB 为 NB2。

## 0.28.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `granger_causality` | R `lmtest::grangertest(effect ~ cause, order=k)` | `tests/test_r_oracles13.py` | F/p 一致；df 取模型 1 的 Res.Df 与 abs(Df) |
| `arch_test` | R `FinTS::ArchTest(x, lags=5, demean=FALSE)` | `tests/test_r_oracles13.py` | LM/p 一致；平方序列滞后回归 |
| `flow_compensate` | R `flowCore::compensate(flowFrame(e), spillover)` | `tests/test_r_oracles13.py` | 三行事件矩阵逐值一致；方阵、标签匹配 |

- 新增 R 包 `lmtest 0.9.40`、`FinTS 0.4.9`；使用已安装的 `flowCore 2.14.2`。
- 参考值：Granger F `395.9681448165 / 211.8084391160 / 146.0148719626`（lag 1/2/3）；ARCH LM `11.4217771216`、p `0.0436298086`；补偿行为 `[1, 0, 5]`、`[1.9897959, 0.1020408, 6]`、`[3.0510204, -0.5102041, 7]`。
- 复现：`python -m pytest -q tests/test_extension21.py tests/test_r_oracles13.py`。
- 边界：Granger 只做双变量、指定滞后阶数的 F 检验；ARCH 不做 GARCH 拟合；flow_compensate 只支持方阵线性溢漏矩阵。

## 环境与缺口

- R 4.3.3；已装 `vegan`、`survival`、`metafor`、`edgeR`、`limma`、`DESeq2`、`fgsea`、`GSVA`、`sva`、`Kendall`、`ALDEx2` 等。
- 未装 `clusterProfiler`、`ANCOMBC`、`glmnet`、`preprocessCore`、`msigdbr`、`org.Hs.eg.db`、`biomaRt`、`rtracklayer`、`Rsamtools`、`ShortRead`、`phangorn`、`survminer`、`timeROC`、`pec`、`rms` 等。它们只影响对应领域；0.20 的 8 个算子不需要这些包。
- Python 侧使用 `statsmodels 0.14.6`、`scipy 1.17.1`；未安装 `pyteomics`/`pingouin` 等。质谱 Reader 用标准库 XML 解析，不依赖 `pyteomics`。
- 后续全量权威对标时，按算子领域选择 R/Python/命令行工具；不能直接对齐的项（如不同 NMDS 应力定义、不同 PH 假设检验实现）必须记录算法差异，不能强行调参拟合。

## 复现命令

```bash
# 纯 Python 与 R 对照（R 缺失时自动 skip）
python -m pytest -q tests/test_extension13.py tests/test_extension13_readers.py tests/test_r_oracles5.py
```

本矩阵只覆盖当前批次；历史批次见 `docs/sop_matrix.md` 的 §18/§19 与对应 R oracle 文件。
