## 0.87.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `arima` | R `stats::arima(order=c(1,0,0), method="ML", include.mean=TRUE)` | `tests/test_r_oracles69.py` | seed 20261113、n=100 AR(1)：R coef **1.316459716 / 0.639954023**、sigma2 **0.6130963**、loglik **-117.6956**、AIC **241.3912**；statsmodels `cov_type="approx"` 对齐；const SE R **0.213974945**；容差 coef/se 1e-4、sigma2 2e-5、loglik/AIC 1e-3 |
| `isotonic` | R `isoreg`（递增/递减） | `tests/test_r_oracles69.py` | x 1..8、y `[1,2.2,1.8,2.7,3.1,2.9,4.2,4]`：递增 fitted `[1,2,2,2.7,3,3,4.1,4.1]`；递减全 **2.7375**；逐值容差 1e-12 |

## 0.86.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `chao1` | R `vegan::estimateR` | `tests/test_r_oracles68.py` | 计数 fixture `[[10,20,30,0],[5,0,15,30],[0,0,0,0],[1,1,1,1]]` 的 Chao1 `[3,3,0,10]`；f2=0 时用偏倚校正式 |
| `rarefaction` | R `vegan::rarefy` | `tests/test_r_oracles68.py` | 同 fixture 的样本总量 60/50/10，depth 10 得 `[2.852110517597176, 2.671547890140520, 3.0]`；深度等于总量时全保留 |

## 0.85.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `aft` | R `survival::survreg(Surv(time,event)~x1+x2, dist="weibull")` | `tests/test_r_oracles67.py` | seed 20261112、n=90、58 events：coef **1.24865535626414 / 0.918466782844872 / -0.434929192384358**，scale **0.913473103084374**，loglik **-120.493434256986**；coef/se/shape 容差 2e-5 |
| `hardy_weinberg` | R `HardyWeinberg::HWExact(..., pvaluetype="selome")` | `tests/test_r_oracles67.py` | 六组 AA/AB/BB 计数，p 从 **0.07767465115912098** 到 **1.1142241805814507e-30**；相对容差 2e-10 |

## 0.84.0

本轮不新增算子/Reader，也不新增外部数值 oracle；验证重点是分类、Reader 元数据、平台标记与目录完整性。新增 `tests/test_catalog_integrity.py`，并保留既有 R/Python oracle 全部通过。全量 pytest：**974 passed, 1 skipped**。

## 0.83.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `dbrda` | R `vegan::dbrda(vegdist(Y, method="bray") ~ x1 + x2)` | `tests/test_r_oracles66.py` | 8×3 计数、2 解释变量：总惯量 **0.29766435057928425**，约束 **0.14785322587790678**，未约束 **0.14981112470137747**，特征值 **0.14271793573379188 / 0.0051352901441149134**；容差 1e-10；解释变量仅中心化，不加截距列 |
| `leave_one_out` | R `metafor::leave1out(rma(yi, vi, method="FE"/"DL"))` | `tests/test_r_oracles66.py` | 8 研究：FE 第一项 estimate **0.23303691756346831**、se **0.13543160584780461**；DL 第一项 estimate **0.24783622694697988**、se **0.22256015182479655**、tau2 **0.20666323998000977**；estimate/se/tau2/I2/Q/Qp 对齐 1e-10 |

## 0.82.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `pcoa` | R `vegan::cmdscale(D, k=4, eig=TRUE)` | `tests/test_r_oracles65.py` | 7×7 非欧距离：正特征值 **5.542135906022611 / 5.317599140996917 / 3.0999555198047037 / 1.348490145693564**；前 3 维坐标按绝对值对齐 1e-5；负特征值不进入坐标 |
| `cca` | R `vegan::cca(Y ~ x1 + x2)` | `tests/test_r_oracles65.py` | 8×3 计数、2 解释变量：总惯量 **0.15765814626171162**，约束 **0.0760530413394101**，未约束 **0.08160510492230152**，特征值 **0.07592386857218954 / 0.00012917276722056823**；特征值/惯量容差 1e-10；R `$CCA$u` 缩放不同，不比较 site scores |

## 0.81.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `inverse_gaussian_regression` | R `stats::glm(family=inverse.gaussian(link="log"))` | `tests/test_r_oracles64.py` | seed 20261110、n=60：coef **0.29112628016820374 / 0.31847495391789 / -0.22659950198706433**，SE **0.1160139475750473 / 0.08959275775038143 / 0.1159005421324707**；deviance **47.62187822182909**，null dev **56.22929763488882**；coef 对齐 3e-5，SE 3e-6；AIC 因 likelihood 常数不同不比较 |
| `betadisper` | R `vegan::betadisper(type="centroid")` + `anova` | `tests/test_r_oracles64.py` | 12 样本两组：group means **0.5432907785733675 / 1.5080518970308538**，F **12.27190000879564**，p **0.0056966678673121976**；距离和特征值对齐 1e-12 |
| `zero_inflated_negative_binomial` | R `pscl::zeroinfl(dist="negbin")` | `tests/test_r_oracles64.py` | seed 20261111、n=220、125 zeros：count coef **0.504542522196694 / 0.35446674816788964 / -0.24305519652093036**，zero coef **-0.5862120388429567 / 0.537950517169738**，alpha **0.7224400229926667**，theta **1.38419795162726**，loglik **-312.2941749228622**；coef 3e-5，loglik 1e-7 |

## 0.80.0

| Reader | 格式 | 对照 | 结论/边界 |
|---|---|---|---|
| `RnkReader` | GSEA `.rnk` | 黄金文件 + 严格负例 | 保留文件顺序；`score` 单列；重复基因、非有限分数拒绝 |
| `ClsReader` | GSEA `.cls` | 黄金文件 + 严格负例 | 类别索引经 label encoder 编码；计数/越界/缺 `#` 拒绝 |
| `GrpReader` | GSEA `.grp` | 黄金文件 + 严格负例 | 与 CLS 共用解析器，保留独立扩展名 |

## 0.79.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `meta_regression` | R `metafor::rma(yi, vi, mods=~x1+x2, method="FE"/"DL")` | `tests/test_r_oracles63.py` | seed 20261109、n=24：fixed coef **0.5582954 / 0.3417866 / -0.2302585**，SE **0.06041857 / 0.05883369 / 0.05093128**，tau2 0，Q **109.27136626848096**，I2 **80.78179058509915**；DL coef **0.5431708 / 0.3468496 / -0.2191853**，tau2 **0.34606677368814776**；tau2 分母为 `tr(P)` |

## 0.78.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `beta_regression` | R `betareg::betareg(y ~ x1 + x2)` | `tests/test_r_oracles62.py` | n=80、phi=8 fixture：coef **0.45218830829562068 / 0.74962773840681951 / -0.52970059447541096**，phi **8.44338203849741475**，SE **0.079304360738738172 / 0.081498782085493882 / 0.082805985258789488**，phi SE **1.2829694348069349**，loglik **44.157923586039978**；statsmodels Newton + EIM 协方差，系数容差 2e-5、loglik 1e-7 |
| `redundancy_analysis` | R `vegan::rda(Y ~ x1 + x2)` | `tests/test_r_oracles62.py` | n=40、4 响应、2 解释变量：总惯量 **5.5116445710705815**，约束 **2.566316831991446**，非约束 **2.945327739079135**，特征值 **2.38249053751312445 / 0.18382629447832174**；n−1 惯量，特征值容差 1e-12 |

## 0.77.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `power_t_test` | R `pwr::pwr.t.test` | `tests/test_r_oracles61.py` | d=0.5、n=64：two-sample power 0.8014595579222542，paired/one-sample 0.9760555768876558；R 0.80145955792232759 / 0.97605557688772915，差异 <1e-12 |
| `power_prop_test` | R `pwr::pwr.2p.test(h=ES.h(.6,.4), n=100)` | `tests/test_r_oracles61.py` | h 0.40271584158066154，power 0.8126408236244113；正态近似双侧 |
| `power_anova` | R `pwr::pwr.anova.test(k=4,n=40,f=.25)` | `tests/test_r_oracles61.py` | power 0.7494045377009664，df 3/156；R 0.74940453777624239，差异 <1e-9 |

## 0.76.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `garch` | Python `arch` 8.0.0 `arch_model(vol="GARCH")` | `tests/test_extension69.py`, `tests/test_r_oracles60.py` | 300 点 GARCH(1,1)：coef 0.12545912769161274 / 0.21557564103295726 / 0.04612526785494381 / 0.7269061346242348，persistence 0.7730314024791786，loglik -417.4502100666318，nobs 300；逐值一致 |
| `var_model` | R `vars::VAR(p=1, type="const")` | `tests/test_r_oracles60.py` | 120×2 VAR(1)：y1 方程 -0.03397482 / 0.39825042 / 0.12134407，y2 方程 0.06367029 / 0.17068698 / 0.40692885，llf -137.21370301647985；系数容差 1e-10 |

## 0.75.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `correspondence_analysis` | R `ca::ca` | `tests/test_r_oracles59.py` | 4×3 计数表：奇异值 **0.34920690627954476 / 0.19981461817371882**，总惯量 **0.16187134502923978**，卡方 **42.89590643274854**，df 6；标准坐标/奇异值逐值一致（1e-12） |
| `tobit` | R `censReg::censReg` | `tests/test_r_oracles59.py` | n=60，11 个左删失：coef **1.10646400866156114 / 0.91970907755316011 / -0.60664699838834946**，se **0.11553127141226120 / 0.11778270999030564 / 0.12791704775948415**，sigma **0.8373168628959122**，loglik **-67.507455881612927**；系数/se 容差 2e-6，loglik 1e-8 |

## 0.74.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cusum_chart` | R `qcc::cusum(sizes=1, decision.interval=5, se.shift=1)` | `tests/test_r_oracles58.py` | 12 点 fixture：center 13.5、sigma 1.3700838168923277；pos 末值 4.4338823529411755、neg 首值 -2.0545882352941174；逐值一致 |
| `ewma_chart` | R `qcc::ewma(sizes=1, lambda=0.2, nsigmas=3)` | `tests/test_r_oracles58.py` | 同一 fixture：首值 12.8、末值 14.688383963136；LCL/UCL 首行 12.677949709864604 / 14.322050290135396；逐值一致 |

## 0.73.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `phillips_perron` | R `urca::ur.pp(type="Z-t", model="constant", lags="short", use.lag=2)` | `tests/test_r_oracles57.py` | 120 点随机游走 fixture：stat **-1.9273077985416451**，p **0.31932569624470114**，nobs 119；R stat **-1.9273080452513796**，差 <1e-6；长程方差带宽实现不同 |
| `dfgls` | R `urca::ur.ers(type="DF-GLS", model="constant", lag.max=2)` | `tests/test_r_oracles57.py` | 同一 fixture：stat **-1.74135623062118**，p **0.08039437046328551**，nobs 117；R stat **-1.7413562306211814**，逐值一致 |
| `arch_lm` | R `FinTS::ArchTest(e, lags=5)` | `tests/test_r_oracles57.py` | 200 个 t(5) 残差：LM **4.186145832492666**，p **0.5229387617060965**，F **0.829270564019495**，F p **0.5303006600082081**；逐值一致 |

## 0.72.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `theil_u` | R `DescTools::UncertCoef(direction=row/column/symmetric)` | `tests/test_r_oracles56.py` | 2×2 [[10,20],[30,40]]：0.006583693 / 0.005975741 / 0.006265003；无置信区间 |
| `dfbetas` | R `stats::dfbetas` | `tests/test_r_oracles56.py` | 8×3 y/x1/x2 fixture 与 R 逐值一致；输出 intercept + 预测变量 |
| `covratio` | R `stats::covratio` | `tests/test_r_oracles56.py` | 8 个样本的 COVRATIO 与 R 一致；最大值在并列的 s6/s7 |

## 0.71.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `zivot_andrews` | R `urca::ur.za(model="intercept", lag=2)` | `tests/test_r_oracles55.py` | 80 点结构突变 fixture：统计量 -3.7254940402358883，p 0.5295691048518368，statsmodels bpidx 57 / R bpoint 58；临界值表不同，只比较统计量 |
| `poisson_means_test` | R `poisson.test` 条件二项精确检验 | `tests/test_r_oracles55.py` | 100/4 vs 50/4：p 5.4475331033925765e-05，rate ratio 2，95% CI 1.4105504610094759–2.8676286550257819；与 scipy E-test 不同 |

## 0.70.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `engle_granger` | R `urca::ur.df`（残差 ADF，`type="none"`，`lags=2`） | `tests/test_r_oracles54.py` | 160 点随机游走 fixture：统计量 -6.365675416103156，p 2.536310715415716e-07；n=160；临界值 -3.96664605 / -3.37482819 / -3.0712318 |
| `johansen` | R `urca::ca.jo`（`type="trace"/"eigen"`，`ecdet="none"`，`K=2`） | `tests/test_r_oracles54.py` | trace 72.01098429 / 4.146971568；max-eig 67.86401273 / 4.146971568；eigen 0.34917798 / 0.02590521；R 的 `@teststat` 为逆序 |

# 权威实现对照矩阵

## 0.69.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `approx_entropy` | R `pracma::approx_entropy` | `tests/test_r_oracles53.py` | 100 点正弦 fixture，ApEn 0.19343740801454112；2 维嵌入、r=0.2*sd |
| `hurst_exponent` | R `pracma::hurstexp(x)$Hs` | `tests/test_r_oracles53.py` | 同一 fixture，H 0.54431529367338694；奇数长度按 hurstexp 约定补齐 |

## 0.68.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `gwet_ac1` | R `irrCAC::gwet.ac1.raw` | `tests/test_r_oracles52.py` | 5×4 fixture，AC1 -0.14427860696517408；R 输出四舍五入到 5 位小数，oracle 容差 1e-5 |
| `brennan_prediger` | R `irrCAC::bp.coeff.raw` | `tests/test_r_oracles52.py` | 同一 fixture，系数 -0.15；未加权 |
| `conger_kappa` | R `irrCAC::conger.kappa.raw` | `tests/test_r_oracles52.py` | 同一 fixture，系数 -0.11650485436893211；未加权 |

## 0.67.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `standardized_residuals` | R `stats::rstandard(lm)` | `tests/test_r_oracles51.py` | fixture x=1..10、y=2+0.5x+[1,-1,2,-2,0,1,-1,2,-2,0]；10 个值逐项相对误差 < 1e-6 |
| `studentized_residuals` | R `stats::rstudent(lm)` | `tests/test_r_oracles51.py` | 同一 fixture；删除残差方差 `s_i²=(SSE-e²/(1-h))/(n-p-1)` |
| `press` | OLS PRESS 公式 / R `hatvalues` 手算 | `tests/test_r_oracles51.py` | PRESS 29.579274620026872，RMSE 1.719862628817397；n=10，p=2 |

## 0.66.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `leverage` | R `stats::hatvalues(lm)` | `tests/test_r_oracles50.py` | x=1..10 的 hat 值 0.34545454545454546…0.34545454545454546；OLS 含截距 |
| `cooks_distance` | R `stats::cooks.distance(lm)` | `tests/test_r_oracles50.py` | x=1..10 的 Cook D 0.074610468585066189…0.017657992565055805；p 含截距 |
| `dffits` | R `stats::dffits(lm)` | `tests/test_r_oracles50.py` | x=1..10 的 DFFITS 0.36790202489736512…0.17652800580145919；使用删除残差方差 |

## 0.65.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `variance_ratio` | R `stats::var.test` | `tests/test_r_oracles49.py` | x=1..5, y=2,4,6,8,10：F 0.25，df 4/4，p 0.20800000000000005，95% CI 0.026029384363481924..2.4011324711807167；每组 >=2、方差非零 |
| `youden_index` | sklearn `roc_curve` + 手算 J | `tests/test_extension58.py` | 阈值 0.4，sens 1.0，spec 0.8，J 0.8，n_pos/n_neg 5/5；二分类标签 + 连续分数 |
| `krippendorff_alpha` | 标准公式 + R `irr::kripp.alpha`（缺失 fixture） | `tests/test_r_oracles49.py` | 完整 nominal -0.1052631578947365、interval -0.20578778135048226；缺失 nominal -0.08130081300812986、interval -0.1192411924119241；R 0.84.1 完整数据分母 bug |

## 0.64.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `risk_ratio` | R 公式 / `epitools::riskratio` | `tests/test_r_oracles48.py` | 表 `[[18,12],[10,20]]`：RR 1.8，95% CI 1.0034442222671074..3.2288790229712867；第 1 行暴露、第 2 行非暴露；零格默认 Haldane +0.5 |
| `odds_ratio` | R 公式 / `epitools::oddsratio(method="wald")` | `tests/test_r_oracles48.py` | OR 3.0，95% CI 1.0461986908532277..8.602572416392574；Woolf log CI |
| `cohens_h` | R `pwr::ES.h` + 正态 CI | `tests/test_r_oracles48.py` | h 0.5411948302444529，95% CI 0.035134305491788975..1.0472553549971169；独立比例 |

## 0.63.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cross_correlation` | R `stats::ccf` | `tests/test_r_oracles47.py` | lags −3..3：0.46271424434198255 / 0.4797494951287023 / 0.43048539150224246 / 0.07044306406400333 / -0.31952605529685163 / -0.47744743421157804 / -0.6312251034754807；`lags < n` |
| `difference_sign` | R `randtests::difference.sign.test` | `tests/test_r_oracles47.py` | x 12 点：z 1.4411533842457842、p 0.14954135458461512；零差分剔除 |
| `bds_test` | Python `statsmodels.tsa.stattools.bds` | `tests/test_extension56.py` | 12 点、max_dim=2、eps=0.5：statistic 4.940627273908729、p 7.787164227744485e-07；R `tseries` 协方差缩放不同，不作为 oracle |

## 0.62.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `fowlkes_mallows` | sklearn `fowlkes_mallows_score` | `tests/test_extension55.py` | A/B 各 9 样本 3 簇：FMI 0.5270462766947299；两分区均至少 2 簇 |
| `homogeneity_completeness_v_measure` | sklearn `homogeneity_completeness_v_measure` | `tests/test_extension55.py` | H 0.5793801642856953、C 0.6000000000000002、V 0.5895098274473051；beta=1 |
| `pair_confusion_matrix` | sklearn `pair_confusion_matrix`；Rand 关系对 R `aricode::RI` | `tests/test_r_oracles46.py` | `[[44,10],[8,10]]`；Rand index 0.75 |

## 0.61.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `acf` | R `stats::acf` | `tests/test_r_oracles45.py` | x=[1,2,3,4,5,4,3,2,1,2,3,4]，lag1..5 0.55503144654088044、-0.05974842767295601、-0.56132075471698117、-0.66666666666666652、-0.33805031446540873；lags<n |
| `pacf` | R `stats::pacf` | `tests/test_r_oracles45.py` | 同一序列，lag1..5 0.55503144654088044、-0.53156095138395143、-0.43409697205350251、-0.21794716741019138、0.0096932454921819424；Yule-Walker |
| `precision_recall_curve` | sklearn `precision_recall_curve` + `average_precision_score` | `tests/test_extension54.py` | AP 1.0；首点 precision 0.625、recall 1、threshold 0.1；末点 precision 1、recall 0、threshold NaN |

## 0.60.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `box_pierce` | R `stats::Box.test(type="Box-Pierce")` | `tests/test_r_oracles44.py` | Q 7.5205292512163302、df 3、p 0.057033307356141538；`n*sum(rho^2)`，lags<n，fitdf<lags |
| `stuart_maxwell_test` | R `DescTools::StuartMaxwellTest` | `tests/test_r_oracles44.py` | 3×3 表 statistic 0.53474320241691853、df 2、p 0.76538859928510916、N 120 |
| `variation_of_information` | R `aricode::NVI` + 熵定义 | `tests/test_r_oracles44.py` | VI 1.5810937501718234、NVI 0.83692987891500414；自然对数，按联合熵归一化 |

## 0.59.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `dunn_index` | R `clusterCrit::intCriteria(X, labels, "Dunn")` | `tests/test_r_oracles43.py` | 6 样本 2 簇 Dunn 30.67572330035593；最小簇间距离/最大簇内直径 |
| `adjusted_mutual_info` | R `aricode::AMI` | `tests/test_r_oracles43.py` | max 归一化 0.33746780635745904；默认 max，可选 arithmetic/geometric/min |
| `silhouette_samples` | R `cluster::silhouette` | `tests/test_r_oracles43.py` | 逐样本 0.9689982614384166、0.9739300984276602、0.9739300984276602、0.9677329920415768、0.9744462659328769、0.9744462659328769 |

## 0.58.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `silhouette_score` | R `cluster::silhouette`（欧氏距离） | `tests/test_r_oracles42.py` | 6 样本 2 簇均值 0.9722473303668445；sklearn 与 R 一致 |
| `adjusted_rand_index` | R `aricode::ARI` | `tests/test_r_oracles42.py` | 0.32432432432432434 |
| `normalized_mutual_info` | R `aricode::NMI` | `tests/test_r_oracles42.py` | arithmetic 0.47870397138568005、geometric 0.4791387674918639、max 0.45914791702724483、min 0.5 |

## 0.57.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `tukey_test` | R `PMCMRplus::tukeyTest` | `tests/test_r_oracles41.py` | 4 组 n=5/6/5/7：B-A p 0.26502273475490234，C-A p 0.00044739595759790696，D-A p 6.5625131024704686e-05；合并 MSE、studentized range |
| `tamhane_t2` | R `PMCMRplus::tamhaneT2Test` | `tests/test_r_oracles41.py` | B-A p 0.26157925285918715，C-A p 0.0028593777811823928；Welch df + Sidak |
| `snk_test` | R `PMCMRplus::snkTest` | `tests/test_r_oracles41.py` | B-A p 0.074054575763289443，C-A p 0.00023621084901115363；step-down range |

## 0.56.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `chacko_test` | R `PMCMRplus::chackoTest` | `tests/test_r_oracles40.py` | 4 组×6：H 5.6716666666666651，df 3，p 0.12872406680233608；每组≥2 |
| `fligner_wolfe` | R `PMCMRplus::flignerWolfeTest(dist="Normal")` | `tests/test_r_oracles40.py` | 对照 A：z 1.9503674363248837，p 0.025566170105179833；正态近似 + 并列校正 |
| `mack_wolfe` | R `PMCMRplus::mackWolfeTest(p=3)` | `tests/test_r_oracles40.py` | 峰值 C：Ap 98，z 1.6001893827313254，p 0.054778288391342869；有并列时精确方差不可用 |

- R 4.3.3；`PMCMRplus` 已安装；复现：`python -m pytest -q tests/test_extension49.py tests/test_r_oracles40.py`。

## 0.55.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `anscombe_glynn` | R `moments::anscombe.test` | `tests/test_r_oracles39.py` | 12 样本：kurt 2.1341104474559254，z -0.42227346311066044，p 0.6728254253719288；n≥8 |
| `bonett_seier` | R `moments::bonett.test` | `tests/test_r_oracles39.py` | 12 样本：tau 4.9861111111111107，z -1.0951999132137393，p 0.27342906371823772；n≥3 |
| `mauchly_test` | R `stats:::mauchly.test.SSD` | `tests/test_r_oracles39.py` | 6×3：W 0.00012919496245979595，chi2 33.329477397827，df 5，p 7.0069860189294373e-06；卡方近似 |

- R 4.3.3；`moments` 已安装；Mauchly 使用 `T=diag(p)`，即检验协方差矩阵的球形性；p<3、n≤p、奇异协方差拒绝。
- 复现：`python -m pytest -q tests/test_extension48.py tests/test_r_oracles39.py`。

## 0.54.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `goldfeld_quandt` | R `lmtest::gqtest` | `tests/test_r_oracles38.py` | 20 样本、fraction=0：GQ 7.8091706001348626，df 8/8，p 0.0043735156064267696；单响应单自变量 |
| `rainbow_test` | R `lmtest::raintest` | `tests/test_r_oracles38.py` | 20 样本、fraction=0.5：Rain 37.09507275139439，df 10/8，p 1.298882331413825e-05；中心子样本 6..15 |

- R 4.3.3；`lmtest` 已安装；两个算子均按 x 排序，保留截距；GQ 的 `fraction` 只支持比例，Rainbow 的 `center` ± `fraction/2` 必须在 [0,1]。
- 复现：`python -m pytest -q tests/test_extension47.py tests/test_r_oracles38.py`。

## 0.53.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `ansari_bradley` | R `stats::ansari.test(exact=FALSE)` | `tests/test_r_oracles37.py` | x=[1..5], y=[1,4,9,16,25]：AB 18，z 1.0392304845413265，p 0.29869755599497028；正态近似、含并列校正 |
| `chisq_out_test` | R `outliers::chisq.out.test` | `tests/test_r_oracles37.py` | [1,2,3,4,5,100]：χ² 4.161359374447157，p 0.04135620027516618；opposite χ² 0.21018646286664547，p 0.6466212955873326，对应 1 |
| `calibration_curve` | 自有分箱实现（对齐 sklearn） | `tests/test_extension46.py` | 20 样本 / 5 箱：均匀分箱边界与每箱预测均值/观测比例 |

- R 4.3.3；Ansari 只对照正态近似分支，精确条件分布未实现；校准曲线无外部 oracle。

## 0.52.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `agostino_skewness` | R `moments::agostino.test` | `tests/test_r_oracles36.py` | x=[1..9,20]：skew 1.6060526914810145，z 2.6471420773508192，p 0.0081175240201695822 |
| `chi_square_gof` | R `stats::chisq.test` | `tests/test_r_oracles36.py` | counts [10,20,30,40]：χ² 20，df 3，p 0.00016974243555282649 |
| `cochran_c_test` | R `outliers::cochran.test` | `tests/test_r_oracles36.py` | 3 组各 5：C 0.95238095238095233，df1 8，df2 4，p 7.4190133887430676e-05 |

- R 4.3.3；`moments`、`outliers` 已安装；Cochran C 要求等组样本量，p 采用 R `pcochran` 右尾。
- 复现：`python -m pytest -q tests/test_extension45.py tests/test_r_oracles36.py`。

## 0.51.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `fligner_killeen` | R `stats::fligner.test` | `tests/test_r_oracles35.py` | 3 组各 6 个：statistic 3.8539129401029886，df 2，p 0.14559063431450478 |
| `mood_scale` | R `stats::mood.test` | `tests/test_r_oracles35.py` | 两样本各 6 个：Z -0.72323757801982935，p 0.46953393562819462；含并列校正 |
| `siegel_tukey` | R `PMCMRplus::siegelTukeyTest` | `tests/test_r_oracles35.py` | 5 vs 5 无并列：W 14，p 0.84126984126984128；有并列时拒绝 |

- R 4.3.3；`PMCMRplus` 已安装；Siegel-Tukey 小样本使用精确秩和分布，`n_a*n_b > 10000` 时退回正态近似并在 info 标记 `exact=false`。
- 复现：`python -m pytest -q tests/test_extension44.py tests/test_r_oracles35.py`。

## 0.50.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `levene_test` | R `DescTools::LeveneTest(center="mean")` | `tests/test_r_oracles34.py` | 15 样本、3 组：F 3.5958295790964074，p 0.059760241554658484；每组至少 2 个有限值 |
| `brown_forsythe` | R `DescTools::LeveneTest(center="median")` | `tests/test_r_oracles34.py` | 同数据：F 0.48166623810748233，p 0.6291982673370824；中位数中心 |
| `barnard_test` | SciPy 1.17.1 `stats.barnard_exact` | `tests/test_extension43.py` | `[[8,2],[1,9]]`：statistic 3.1462660248284626，p 0.0018215179443359397，OR 36，n 20 |

- R 4.3.3；`DescTools` 已安装；Barnard 为 SciPy 无条件精确算法，不声称与 R `DescTools::BarnardTest` 的 CSM 数值完全一致。
- 复现：`python -m pytest -q tests/test_extension43.py tests/test_r_oracles34.py`。

## 0.49.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `durbin_test` | R `PMCMRplus::durbinTest(m)` | `tests/test_r_oracles33.py` | 4 块×4 处理、k=3、r=3：chi2 7.5，df 3，p 0.057558451972636406；平衡不完全区组 |
| `skillings_mack` | R `PMCMRplus::skillingsMackTest(m)` | `tests/test_r_oracles33.py` | 5 块×4 处理、15 个观测：chi2 9.4090909090909083，df 3，p 0.02431840851015896；要求共现图连通 |
| `cuzick_test` | R `PMCMRplus::cuzickTest(x, g)` | `tests/test_r_oracles33.py` | A/B/C 各 6：z 3.5418343613549821，p 0.00039735490558644653，T 407.5；不做并列校正 |

- R 4.3.3；`PMCMRplus` 来自 USTC CRAN，依赖 `multcompView/Rmpfr/SuppDists/kSamples/BWStest` 已安装。
- 复现：`python -m pytest -q tests/test_extension42.py tests/test_r_oracles33.py`。

本页记录扩展算子与外部权威实现的对标方式。原则：优先使用同语义的成熟实现；数值差异必须能由算法差异、参数或浮点精度解释；不能对标的项要明确写出原因。

## 0.48.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `conover_test` | R `DescTools::ConoverTest(x, g)` | `tests/test_r_oracles32.py` | B-A rank diff 4.8333333333333339，Holm p 0.010462063490453718；C-A p 2.5080247917311833e-05；C-B p 0.0044497715042364737 |
| `games_howell` | R `PMCMRplus::gamesHowellTest(x, g)` | `tests/test_r_oracles32.py` | B-A q 3.9279220242478630，p 0.047125923759940624；C-A p 0.00018923503262868735；C-B p 0.010381720683943052 |
| `quade_test` | R `stats::quade.test(m)` | `tests/test_r_oracles32.py` | 5 块×3 处理：F 18，df 2/8，p 0.0010928215285841132 |

- R 4.3.3；`DescTools`、`PMCMRplus` 来自 USTC CRAN；`PMCMRplus` 的依赖 `multcompView/Rmpfr/SuppDists/kSamples/BWStest` 已安装。
- 复现：`python -m pytest -q tests/test_extension41.py tests/test_r_oracles32.py`。

## 0.47.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `scheffe_test` | R `DescTools::ScheffeTest(aov(x ~ g))` | `tests/test_r_oracles31.py` | B-A diff 3，95% CI 0.068774863320079316..5.9312251366799238，p 0.044508331150382108 |
| `nemenyi_test` | R `DescTools::NemenyiTest(x, g)` | `tests/test_r_oracles31.py` | B-A rank diff 4.8333333333333339，p 0.2595187845582884734 |
| `pettitt_test` | R `trend::pettitt.test` | `tests/test_r_oracles31.py` | U 98，p 0.0020978278652555764，变点 9/11 |

- R 4.3.3；`DescTools`、`trend` 来自 USTC CRAN。
- 复现：`python -m pytest -q tests/test_extension40.py tests/test_r_oracles31.py`。

## 0.46.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `sen_slope` | SciPy 1.17.1 `stats.theilslopes` | `tests/test_extension39.py` | slope 1.98，intercept 0.26，95% CI 1.9..2.025；至少 3 个完整对，x 非常量 |
| `mahalanobis_distance` | R base `mahalanobis` | `tests/test_r_oracles30.py` | 8×3 距离 3.0759981851181237..3.1839836660619767；样本协方差 ddof=1，输出平方距离 |
| `box_m` | R `biotools::boxM` | `tests/test_r_oracles30.py` | 3 组×8、p=2：M 0.8753278628690389，chi2 0.7549123896701234，df 6，p 0.9932284578587726 |

- `mahalanobis_distance`、`box_m` 使用 R 4.3.3 与 `biotools` 4.3；`sen_slope` 无 R oracle，直接对照 SciPy。
- 复现：`python -m pytest -q tests/test_extension39.py tests/test_r_oracles30.py`。

## 0.45.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `binomial_test` | SciPy 1.17.1 `stats.binomtest` | `tests/test_extension38.py` | k=7,n=10,p0=0.5：p 0.34375；Clopper-Pearson 95% CI 0.3475471499399921..0.9332604888222655 |
| `mood_median_test` | SciPy 1.17.1 `stats.median_test` | `tests/test_extension38.py` | 三组 [1..5]/[2..6]/[5..9]：statistic 7.8，p 0.020241911445804395，median 5；默认 ties=below、Yates 校正 |
| `boschloo_exact` | SciPy 1.17.1 `stats.boschloo_exact` | `tests/test_extension38.py` | [[8,2],[1,9]]：p 0.0018352604919337544，Fisher p 0.002738747320790664，OR 36 |

- 0.45 无 R oracle；三个算子直接对照 SciPy 1.17.1 的权威实现。
- 复现：`python -m pytest -q tests/test_extension38.py`。

## 0.44.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cox_stuart_test` | R `randtests::cox.stuart.test` | `tests/test_r_oracles29.py` | t 10，n 10，p 0.001953125；奇数长度丢中间值，并列对剔除 |
| `grubbs_test` | R `outliers::grubbs.test` | `tests/test_r_oracles29.py` | G 2.709117334893635，U 0.19267515923566875，p 0.00093820829159652064；离群值 25，n=11 |
| `anderson_darling` | R `nortest::ad.test` | `tests/test_r_oracles29.py` | A 0.18980837048798804，p 0.88712429103709245，n=20；估计均值/标准差，n>=8 |

- 使用已安装的 `randtests`、`outliers`、`nortest`。
- 复现：`python -m pytest -q tests/test_extension37.py tests/test_r_oracles29.py`。

## 0.43.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `page_test` | R `DescTools::PageTest` | `tests/test_r_oracles28.py` | L 232，p 8.0199816518308664e-06，8 块 × 4 处理；精确分布；正态分支 L 7480，p 2.3535702950702129e-18 |
| `mardia_test` | R `psych::mardia` | `tests/test_r_oracles28.py` | n=60，p=3；b1p 0.12217681576367496，b2p 10.404188899192361；p.skew 0.99957224997298111，p.kurt 0.0011551495235322395 |
| `turning_point_test` | R `randtests::turning.point.test` | `tests/test_r_oracles28.py` | turns 8，z 2.2103158559821505，p 0.027083248944000271，n=10 |

- 使用已安装的 `DescTools`、`psych`、`randtests`。
- 复现：`python -m pytest -q tests/test_extension36.py tests/test_r_oracles28.py`。
- 边界：Page 完整区组/无并列值；Mardia 协方差可逆；Turning Point 无相邻并列值。

## 0.42.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `shapiro_wilk` | R `stats::shapiro.test` | `tests/test_r_oracles27.py` | W 0.96016416316107545，p 0.54713405582814623，n 20；AS R94 近似、3–5000 个样本 |
| `lillie_test` | R `DescTools::LillieTest` | `tests/test_r_oracles27.py` | D 0.081749071087235753，p 0.97813612285642071，n 20；Dallal-Wilkinson p 近似、n>=5 |
| `moses_test` | R `DescTools::MosesTest` | `tests/test_r_oracles27.py` | S 8，p 0.0015479876160990713，n_a=n_b=10，extreme=1；平均秩、精确组合 p |

- 使用已安装的 `DescTools` 与 R `stats`。
- 复现：`python -m pytest -q tests/test_extension35.py tests/test_r_oracles27.py`。
- 边界：Shapiro-Wilk/Lilliefors 不提供 exact p；Moses 仅两组、不做置换/CI。

## 0.41.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `bhapkar_test` | R `DescTools::BhapkarTest` | `tests/test_r_oracles26.py` | Bhapkar chi2 0.68890103881902676，df 2，p 0.70860961374150644，n 60；3x3 方表、S/(1-S/N) 校正 |
| `von_neumann` | R `DescTools::VonNeumannTest` | `tests/test_r_oracles26.py` | VN 0.1212121212121212，z -3.3259311751475229，p 0.00088123685283041943；正态近似、默认 unbiased |
| `shapiro_francia` | R `DescTools::ShapiroFranciaTest` | `tests/test_r_oracles26.py` | W 0.97684303482122625，p 0.81248335763278823，n 20；正态化近似、仅 5–5000 个样本 |

- 使用已安装的 `DescTools`。
- 复现：`python -m pytest -q tests/test_extension34.py tests/test_r_oracles26.py`。
- 边界：Bhapkar 不提供 CI；Von Neumann 不提供 exact p；Shapiro-Francia 不提供 exact p。

## 0.40.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `van_waerden` | R `DescTools::VanWaerdenTest` | `tests/test_r_oracles25.py` | chi2 6.349304，df 1，p 0.01174273；仅两组、平均秩、正态得分 |
| `bartels_rank` | R `DescTools::BartelsRankTest` | `tests/test_r_oracles25.py` | RVN 0.1090909，z -3.2509408，mu 2，var 0.3383165，p 0.001150238；n>=10、正态近似 |
| `woolf_test` | R `DescTools::WoolfTest` | `tests/test_r_oracles25.py` | X2 0.1481616，df 2，p 0.9285967；2x2xk、零格 +0.5、无三阶交互 |

- 使用已安装的 `DescTools`。
- 复现：`python -m pytest -q tests/test_extension33.py tests/test_r_oracles25.py`。
- 边界：Van der Waerden 仅接受两组；Bartels 无 exact p；Woolf 仅 2x2xk、不做三阶交互。

## 0.39.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `hotelling_t2` | R `DescTools::HotellingsT2Test` | `tests/test_r_oracles24.py` | F 22.131694828469026，df 3/4，p 0.0059380028788470485；T² 99.592610；合并协方差、F 近似 |
| `yuen_test` | R `DescTools::YuenTTest(trim=0.2)` | `tests/test_r_oracles24.py` | t -0.566987210046772，df 10，p 0.5832249832837027，diff -1.0，95% CI -4.9297867967823645/2.9297867967823645；Winsorized 方差、Welch df |
| `g_test` | R `DescTools::GTest(correct="none")` | `tests/test_r_oracles24.py` | G 12.750352918064657，df 4，p 0.012562279689834366，n=100；无 Yates/Williams 校正 |

- 使用已安装的 `DescTools`。
- 复现：`python -m pytest -q tests/test_extension32.py tests/test_r_oracles24.py`。
- 边界：Hotelling 要求完整样本、满秩合并协方差、F 近似；Yuen 默认 `trim=0.2`，不提供 exact p；G-test 仅二维列联表、无校正。

## 0.38.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `somers_d` | R `DescTools::SomersDelta` | `tests/test_r_oracles23.py` | D(row) 0.44885945548197204，D(column) 0.45218680504077097，concordant/discordant 787/177；direction 决定被解释变量 |
| `goodman_kruskal_gamma` | R `DescTools::GoodmanKruskalGamma` | `tests/test_r_oracles23.py` | gamma 0.63278008298755184，concordant/discordant 787/177；对称关联，不提供 CI |
| `kendall_w` | R `DescTools::KendallW(correct=FALSE)` | `tests/test_r_oracles23.py` | W 0.84444444444444444，chisq 10.133333333333333，df 4，p 0.038240605326664866，S 76；列排名、无并列校正 |

- 使用已安装的 `DescTools`。
- 复现：`python -m pytest -q tests/test_extension31.py tests/test_r_oracles23.py`。
- 边界：三个算子均只接受完整列联表/评分矩阵；不做事后比较，不提供 bootstrap/CI。

## 0.37.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cramer_v` | R `DescTools::CramerV` | `tests/test_r_oracles22.py` | V 0.36324157862838946，chisq 13.194444444444445，df 2，n=100；二维列联表 |
| `jonckheere_terpstra` | R `DescTools::JonckheereTerpstraTest(exact=FALSE)` | `tests/test_r_oracles22.py` | statistic 49.5，z 3.1980107453341566，p 0.0013837912401648556；正态近似，无 exact p |
| `varimax_rotation` | R `stats::varimax` | `tests/test_r_oracles22.py` | 旋转矩阵、旋转后载荷与 SS loadings 对齐；算法迭代容差导致约 3e-8 相对差异 |

- 使用已安装的 `DescTools` 与 R `stats`。
- 复现：`python -m pytest -q tests/test_extension30.py tests/test_r_oracles22.py`。
- 边界：Cramér's V 不做事后比较；JT 使用正态近似；varimax 仅正交旋转，不做因子数选择。

## 0.36.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `kmo_test` | R `psych::KMO` | `tests/test_r_oracles21.py` | MSA overall 0.691341995940012；MSAi 0.622853474145 / 0.606878691663 / 0.829270272548 / 0.746501028684；完整样本，p≥2 |
| `bartlett_sphericity` | R `psych::cortest.bartlett` | `tests/test_r_oracles21.py` | chisq 62.6586540137764，df 6，p 1.2954623992175e-11，n=12；要求相关矩阵正定 |

- 使用已安装的 `psych 2.6.9`。
- 复现：`python -m pytest -q tests/test_extension29.py tests/test_r_oracles21.py`。
- 边界：只做可分析性诊断，不选择因子数、不旋转、不输出载荷；KMO 对缺失采用完整样本。

## 0.35.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `cronbach_alpha` | R `psych::alpha(check.keys=FALSE)` | `tests/test_r_oracles20.py` | raw 0.980952380952381，std 0.981872040600713，average_r 0.931228237555108；完整样本，不输出 CI |
| `canonical_correlation` | R `stats::cancor` | `tests/test_r_oracles20.py` | 相关系数 0.999512503815628 / 0.063233134692047；QR+SVD，完整样本 |
| `runs_test` | R `randtests::runs.test` | `tests/test_r_oracles20.py` | z 0.654653670708，p 0.512690760262，runs 6，n1/n2 7/3；中位数阈值、正态近似、无 exact p |

- 使用已安装的 `psych 2.6.9`、`randtests 1.0.2`。
- 复现：`python -m pytest -q tests/test_extension28.py tests/test_r_oracles20.py`。
- 边界：alpha 不提供 bootstrap/Feldt CI；canonical 不输出系数/结构载荷；runs 不做连续性校正或 exact p。

## 0.34.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `roc_comparison` | R `pROC::roc.test(method="delong")` | `tests/test_r_oracles19.py` | AUC a/b 0.8025/0.8850，差值 -0.0825，z -2.268139214153，p 0.02332072292964，CI -0.1537906103..-0.0112093897；要求同一样本、较高分数为阳性 |
| `cochran_q` | R `DescTools::CochranQTest` | `tests/test_r_oracles19.py` | Q 0.2857142857，df 2，p 0.8668778997501816，n=10，k=3；宽表二分类完整样本，不做事后比较 |

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

## 0.29.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `breusch_godfrey` | R `lmtest::bgtest(fit, order=1, type="Chisq")` | `tests/test_r_oracles14.py` | LM/p/df 一致；同时输出 statsmodels F 统计量 |
| `reset_test` | R `lmtest::resettest(fit, power=2, type="fitted")` | `tests/test_r_oracles14.py` | F/p/df 一致；拟合值幂次增广 |
| `harvey_collier` | R `lmtest::harvtest(fit)` | `tests/test_r_oracles14.py` | t/p/df 一致；递归残差 |

- 使用已安装的 `lmtest 0.9.40`，无需新增 R 包。
- 参考值：BG LM `2.1242989892`、p `0.1449790984`、F `2.0410720144`；RESET F `14.0018972885`、p `0.0005056802`、df 1/46；Harvey-Collier t `0.4877593042`、p `0.6280371065`、df 46。
- 复现：`python -m pytest -q tests/test_extension22.py tests/test_r_oracles14.py`。
- 边界：三者共用同一 OLS 设计矩阵；BG 是序列相关检验，RESET 是函数形式检验，Harvey-Collier 是线性性检验；不要把它们当作因果识别或稳健推断。

## 0.30.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `multinomial_logit` | R `nnet::multinom(factor(y) ~ x1 + x2)` | `tests/test_r_oracles15.py` | 系数/SE 对齐；第一水平为 reference |
| `conditional_logit` | R `survival::clogit(y ~ x1 + x2 + strata(stratum))` | `tests/test_r_oracles15.py` | 系数/SE 对齐；每个 stratum 恰好一个事件 |
| `robust_regression` | R `MASS::rlm(y ~ x1 + x2, psi=psi.huber)` | `tests/test_r_oracles15.py` | 系数/SE/scale 对齐；Huber M 估计 |

- 使用已安装的 `nnet`、`survival`、`MASS`，无需新增 R 包。
- 参考值：多项 logit 系数 `-0.0785675 / 0.6947102 / 0.4630492`（outcome 2）与 `-0.0353596 / -0.3482974 / 1.1293976`（outcome 3）；条件 logit 系数 `1.0291703 / -0.9972766`，SE `0.5022442 / 0.4568622`；稳健回归系数 `0.9672461 / 1.8805607 / -0.5415845`，scale `0.3079868`。
- 复现：`python -m pytest -q tests/test_extension23.py tests/test_r_oracles15.py`。
- 边界：多项 logit 使用 softmax 参数化，不输出个体预测；条件 logit 不做分层随机效应；稳健回归不输出权重诊断图。

## 0.31.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `gamma_regression` | R `glm(y ~ x1 + x2, family=Gamma(link="log"))` | `tests/test_r_oracles16.py` | 系数/SE 对齐；MLE 尺度参数 |
| `zero_inflated_poisson` | R `pscl::zeroinfl(y ~ x | z, dist="poisson")` | `tests/test_r_oracles16.py` | count/zero 系数对齐；零模型默认仅截距 |

- 使用已安装的 base R 与 `pscl 1.5.9`；`quantreg 6.1` 也已安装，但 0.31 不重复实现既有 `quantile_regression`。
- 参考值：Gamma 系数 `0.4403480 / 0.3146126 / -0.2057134`，SE `0.05692901 / 0.05703248 / 0.04923079`；ZIP count `1.0500853 / 0.4181325`，zero `-0.7452351 / 1.0384099`。
- 复现：`python -m pytest -q tests/test_extension24.py tests/test_r_oracles16.py`。
- 边界：Gamma 为 log link、固定 shape 的 MLE；ZIP 的零模型可加 `zero_predictors`，计数模型支持分类预测；不输出个体拟合值/残差。

## 0.32.0

| Operator | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `intraclass_correlation` | R `irr::icc` | `tests/test_r_oracles17.py` | ICC(A,1) 0.6282403440；F 16.0425178877；p 5.9546426626e-08；CI -0.0850675490..0.8923981941；r0=0 |
| `concordance_correlation` | R `DescTools::CCC` | `tests/test_r_oracles17.py` | CCC 0.6161839；CI 0.4425713..0.7452724；s.shift 1.665079；l.shift 0.9898274；C.b 0.616255 |

- 使用已安装的 `irr 0.85`、`DescTools`；`mcr 1.3.3.1` 已在 0.33 用于 Passing-Bablok/Deming 点估计。
- 复现：`python -m pytest -q tests/test_extension25.py tests/test_r_oracles17.py`。
- 边界：ICC 仅支持完整样本与 r0=0；不做缺失插补；CCC 使用 z-transform CI，不做 bootstrap；两者都不输出个体预测。

## 0.33.0

| 算子 | 权威实现 | 对照测试 | 结论/边界 |
|---|---|---|---|
| `passing_bablok` | R `mcr::mcreg(method.reg="PaBa")` | `tests/test_extension26.py`, `tests/test_r_oracles18.py` | 点估计 slope/intercept 精确匹配；不输出 CI，不做负值/重复测量校正 |
| `deming_regression` | R `mcr::mcreg(method.reg="Deming", error.ratio=1)` | `tests/test_extension26.py`, `tests/test_r_oracles18.py` | 点估计匹配；固定误差比，要求正 `error_ratio` 与非零协方差；不输出 CI |

- 使用已安装的 `mcr 1.3.3.1`。
- 复现：`python -m pytest -q tests/test_extension26.py tests/test_r_oracles18.py`。
- 边界：本批只承诺点估计；R `mcr` 的 PaBa CI 由 C 实现，Deming 的有限样本 SE 约定不同，不能强行对齐。

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
