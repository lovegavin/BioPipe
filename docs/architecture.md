# BioPipe 架构总览

本文让读者在不通读源码的情况下理解仓库：BioPipe 是什么、数据如何流动、模块边界在哪、改一个功能应看哪里。

## 1. 一句话与边界

BioPipe 是**本地生信流水线引擎 + Studio 可视化 + Agent/CLI 接口**。它消费标准格式文件，组装 `Form`（带维度/标签/元数据的多维数组），通过算子和契约生成结果、图片和报告。

它**不负责**自动理解生物学问题、自动识图、自动写论文结论，也不内置 AI 服务；LLM/Agent 是外部调用者。

> **价值主张**：一个巨大、可维护、经过验证的工具集，让 agent 以最低成本调用分析，而不必自己写代码——从而避免生成实现时的逻辑错误和额外 token 消耗。支撑手段与设计判断见 [vision.md](vision.md)。

## 2. 执行流

### 2.1 CLI / 任务

```text
task.yaml
  → load_manifest()            校验 sources/steps 结构
  → Context                  注册 source、运行目录、内存、事件
  → Runner                   按顺序执行 steps
  → Reader                   解析 source → Form
  → Step.run()               Form → Form / report / figure
  → outputs/                 run_summary、steps/*.json、figures/*.png
```

### 2.2 Studio

```text
React Graph
  → /api/validate / /api/contracts   静态检查
  → compile_graph()                   Graph → 确定性 manifest
  → /api/jobs                         写入 job 目录
  → scripts/run.py                   独立 worker 进程执行
  → /api/jobs/{id}/exports|figures    结果回读
```

### 2.3 导入任务

```text
YAML / JSON
  → /api/import
  → import_manifest()         YAML → Graph；自动定位项目/任务输入
  → 前端画布                  用户检查/微调
  → compile_graph()           Graph → manifest
```

## 3. 四个核心协议

完整规范见 [protocol_suite.md](protocol_suite.md)。

| 协议 | 核心对象 | 关键点 |
|---|---|---|
| Manifest | `task.yaml` | `sources` + `steps`；相对/绝对路径；输出名唯一 |
| Reader | `Reader` | 格式语义、坐标基准、缺失、编码、压缩、sibling、磁盘/流式 |
| Operator/Step | `Step` | 输入/输出契约、参数 schema、输出模式、确定性、内存 |
| Form | `Form` | `data` + `dims` + `labels` + `info` + `axis_info`；标签是唯一对齐依据 |

### 3.1 Form 的关键不变量

- `data.ndim == len(dims)`;
- 每个 dim 的 `labels` 是 `{label: position}`，position 连续、唯一；
- `axis_info[dim]` 中的字段必须与轴平行；
- 坐标/计数保持精确；浮点只在可证明无损时压缩；
- 缺失值必须由 `info["missing_code"]` 或 NaN 明确声明；
- 不静默改标签、顺序、编码或缺失语义。

### 3.2 契约

- `port`、`param`、`MISSING` 组成端口 DSL；
- 三态兼容：`compatible` / `incompatible` / `unknown`；
- 静态检查 + 运行时校验；
- 输出模式：`passthrough`、`transform`、`subset`、`project`、`choose`、`declare`、`rename`、`transpose`、`concat`、`attach`、`report`、`none` 等；
- 参数必须严格；未知参数报错；`output` 和 `_input_names` 是引擎边界参数，不是算子 schema 参数。

## 4. 模块地图

| 路径 | 职责 | 典型改动 |
|---|---|---|
| `src/core/` | `Form`、契约、错误、数值精度 | 核心数据语义、契约扩展 |
| `src/reader/` | Reader 路由、格式解析、编码、磁盘/流式 | 新格式、格式 bug、压缩/sibling |
| `src/task/` | manifest、Context、Runner、Step、内存/资源 | 执行语义、参数校验、资源 |
| `src/task/step/steps/` | 内置算子实现 | 新算子、数学修复 |
| `src/web/` | FastAPI、Graph 编译、路线、任务、资产 | 导入/导出、Studio 后端 |
| `frontend/src/` | React 画布、检查器、结果 | 可视化交互 |
| `biopipe/` | CLI、注册表、包、插件、`inspect` | 命令行、注册表、Agent 接口 |
| `biopipe_sdk/` | 公开 SDK、schema、测试辅助 | 外部扩展 |
| `desktop/` | WinForms/WebView2 宿主 | Windows 桌面启动 |
| `scripts/` | `run.py`、`studio.py`、registry、文档生成 | 入口/工具 |
| `tasks/` | 示例和自定义任务 | 新分析示例 |
| `routes/` | 可复用路线模板 | 新路线 |
| `tests/` | 单元、契约、SOP、路线 | 测试 |

### 4.1 “我要改 X，应该看哪里”

| 需求 | 先看 | 再改 |
|---|---|---|
| 新文件格式 | `src/reader/base.py`、`src/reader/__init__.py` | `src/reader/readers/` + 文档/测试 |
| Reader 坐标/缺失 bug | 该 Reader 页 + `docs/reference/readers/` | Reader + 精确 fixture |
| 新算子 | `src/task/step/base.py`、`operator_protocol.md` | `src/task/step/steps/` + schema/contracts + tests |
| 参数校验 | `biopipe_sdk/protocol.py`、`runner.py` | schema/descriptor/测试 |
| Studio 导入 | `src/web/graph.py`、`src/web/api.py` | 前后端 + 回归 |
| 路线编译 | `src/web/graph.py`、`routes.py` | Graph/compile 测试 |
| 内存/资源 | `src/task/memory/` | 预算/准入/spill 测试 |
| Agent 接口 | `biopipe/cli.py`、`docs/agent_api.md` | CLI/MCP + 测试 |
| 文档 | `docs/README.md`、本文件 | 生成器/权威页 |

## 5. 注册表与扩展

- `src/task/step/steps/*.py` 与 `src/reader/readers/*.py` 是内置实现；
- `registry build` 生成 `biopipe/builtin_packages.json` 与 `src/web/builtin_routes.json`；
- `routes/**/task.yaml` 是可复用路线；
- 外部扩展通过 `biopipe_sdk`：单文件 drop-in、wheel、route；
- 扩展不得修改引擎、手改 JSON 索引、依赖私有路径；
- 每个扩展必须有严格 schema、契约、文档页、测试和 owner/version pin。

## 6. 测试与证据

| 层 | 内容 | 命令 |
|---|---|---|
| 单元/契约 | 小矩阵、端口、schema | `python -m pytest -q` |
| 独立 SOP | 外部库/手算/独立解析器 | `python -m pytest -q tests/sop` |
| 主题 verify | 统计/遗传/序列/区间/GO | `python tasks/verify_*.py` |
| demo | 真实数据端到端 | `python tasks/*_demo/test_*.py` |
| 注册表 | 声明/生成物一致性 | `python -m biopipe registry check` |
| 文档 | 参考页完整性 | `python scripts/build_reference_docs.py --check` |

证据分级和缺口见 [sop_matrix.md](sop_matrix.md)。原则：**没有独立 oracle 的算子不标 stable**。

## 7. 当前能力与边界

- Reader：CSV/TSV/TXT/Parquet、Excel、BED/GFF3/GTF/GAF、FASTA/FASTQ、MTX、H5AD/10x H5、VCF/BCF、PLINK1/2、BGEN、GMT/Loom/BIOM、HDF5/Zarr、SAM/PAF/BEDPE、Clustal/NEXUS/Newick/Phylip/Stockholm、GenBank/PDB、PED/GFA、MAF/chain、BigWig、FCS/AB1；
- 算子：QC、变换、统计、生存、遗传、单细胞、序列、注释、区间、微生物、ML、绘图、GO；
- 0.8.0 新增：GSEA/ORA、单细胞 doublet/pseudobulk/marker score、GWAS meta/PRS、蛋白组 rollup/moderated t、微生物 ANCOM-style/ALDEx-style；
- 0.9.0 新增：ComBat 批次校正、ssGSEA 基因集打分，以及单细胞去批次和 RNA-seq ssGSEA 两条 route；
- 0.10.0 新增：31 个统计/机器学习算子、13 个格式 Reader；核心层不变，扩展通过声明、registry 和参考页完成；
- 0.11.0 新增：10 个投影/统计算子、6 个格式 Reader（PAF/SAM/BEDPE/cytoband/Clustal/NEXUS）；核心层不变；
- 0.12.0 新增：UMAP、配对/单样本 t 检验、z-score/min-max/softmax，以及 MAF/UCSC chain Reader；核心层不变；
- 0.14.0 新增：距离相关、偏相关、VIF、分位数/幂变换、稳健缩放、缩尾、秩变换；BAM/CRAM/BigWig/PED/GFA Reader；核心层不变；
- 0.15.0 新增：Mantel、PLS 回归、分位数回归、bootstrap CI、silhouette、互信息；GenBank/PDB/Zarr/BCF Reader；核心层不变；
- 0.16.0 新增：DBSCAN、层次聚类、GMM、孤立森林、Cramér–von Mises、Welch ANOVA、Tukey HSD、C-index、分类指标；WIG/broadPeak/GFF2/mmCIF/OBO/SDF Reader；核心层不变；
- 0.18.0 新增：反向互补、翻译、密码子使用、限制性酶切位点、蛋白性质；PCA loadings、HVG、细胞周期评分、Hudson Fst、GRM 亲缘矩阵、RMST、peptide q-value、McNemar、Kendall tau；FAM/BIM/HapMap/MOL/XYZ/GRO/PSL/genePred/MGF/HMMER domtbl Reader；核心层不变；
- 0.19.0 新增：TMM 归一化、limma 风格批次效应移除、Mantel-Haenszel、Cochran-Armitage、TOST 等价检验、Bland-Altman、竞争风险累积发生率；mzML/mzXML/mzTab Reader；MGF 空峰谱 precursor 修复；核心层不变；
- 0.20.0 新增：Cohen/Fleiss kappa、Breusch-Pagan、Durbin-Watson、Egger 检验、ANOSIM、Procrustes、偏 Mantel；mzIdentML/pepXML/mzDATA/protXML Reader；核心层不变；
- 0.21.0 新增：Storey q-value、DeLong AUC、Dunn 检验、决策曲线、有序 logistic、线性混合模型、Hosmer-Lemeshow、Stuart-Maxwell；核心层不变；
- 0.22.0 新增：FCS 流式细胞术与 AB1 Sanger 测序 Reader；核心层不变；
- 0.23.0 新增：时间依赖 AUC、Brier 与积分 Brier 三个生存预测算子；核心层不变；
- 0.24.0 新增：校准截距/斜率、连续 NRI、IDI 三个临床预测评估算子；核心层不变；
- 0.25.0 新增：White 异方差、Chow 结构突变、Ljung-Box 自相关三个回归/时间序列诊断算子；核心层不变；
- 0.26.0 新增：流式细胞术 arcsinh 变换与二维矩形门控两个算子；核心层不变；
- 0.27.0 新增：ADF/KPSS 平稳性检验、Poisson 回归、负二项回归四个统计算子；核心层不变；
- 0.28.0 新增：Granger 因果、ARCH 检验、流式溢漏补偿三个算子；核心层不变；
- 0.29.0 新增：Breusch-Godfrey、RESET、Harvey-Collier 三个回归诊断算子；核心层不变；
- 0.30.0 新增：多项 logit、条件 logit、Huber 稳健回归三个回归模型；核心层不变；
- 0.31.0 新增：Gamma 回归、零膨胀 Poisson 两个回归模型；核心层不变；
- 0.32.0 新增：ICC（组内相关）、Lin's CCC（一致性相关系数）两个可靠性算子；核心层不变；
- 0.33.0 新增：Passing-Bablok 与 Deming 方法学一致性回归两个算子；核心层不变；
- 0.34.0 新增：配对 ROC 比较（DeLong）与 Cochran Q 两个配对/匹配检验算子；核心层不变；
- 0.35.0 新增：Cronbach's alpha、典型相关、Wald–Wolfowitz runs test 三个可靠性/多变量算子；核心层不变；
- 0.36.0 新增：KMO 取样适切性与 Bartlett 球形检验两个因子可分析性诊断算子；核心层不变；
- 0.37.0 新增：Cramér's V、Jonckheere-Terpstra 有序秩检验、varimax 正交旋转三个效应量/多变量算子；核心层不变；
- 0.43.0 新增：Page 有序备择检验、Mardia 多元正态性检验、Turning Point 序列随机性检验三个算子；核心层不变；
- 0.47.0 新增：Scheffe 事后比较、Nemenyi 事后比较、Pettitt 变点检验三个算子；核心层不变；
- 0.48.0 新增：Conover 事后比较、Games-Howell 事后比较、Quade 区组秩检验三个算子；核心层不变；
- 0.52.0 新增：D'Agostino 偏度检验、Pearson χ² 拟合优度、Cochran C 方差离群检验三个算子；核心层不变；
- 0.53.0 新增：Ansari-Bradley 秩尺度检验、χ² 方差离群检验、分箱校准曲线三个算子；核心层不变；
- 0.54.0 新增：Goldfeld-Quandt 异方差检验、Rainbow 线性偏离检验两个算子；核心层不变；
- 0.59.0 新增：Dunn 指数、调整互信息、逐样本轮廓系数三个聚类验证/一致性算子；核心层不变；
- 0.60.0 新增：Box-Pierce 自相关检验、Stuart-Maxwell 边际齐性检验、变异信息三个算子；核心层不变；
- 0.61.0 新增：ACF、PACF、precision-recall 曲线三个序列/评估算子；核心层不变；
- 0.62.0 新增：Fowlkes-Mallows、同质/完整/V-measure、成对混淆矩阵三个聚类一致性算子；核心层不变；
- 0.63.0 新增：互相关函数、BDS 非线性依赖、差分符号检验三个时间序列诊断算子；核心层不变；
- 0.64.0 新增：风险比、比值比、Cohen's h 三个 2×2 表效应量算子；核心层不变；
- 0.66.0 新增：OLS 杠杆值、Cook 距离、DFFITS 三个回归影响诊断算子；核心层不变；
- 0.67.0 新增：标准化残差、学生化残差、PRESS 三个 OLS 残差诊断算子；核心层不变；
- 0.68.0 新增：Gwet AC1、Brennan-Prediger、Conger kappa 三个评分者一致性系数；核心层不变；
- 0.69.0 新增：近似熵、简单 R/S Hurst 指数两个非线性序列算子；核心层不变；
- 0.70.0 新增：Engle-Granger 残差协整、Johansen 迹/最大特征值协整两个时间序列算子；核心层不变；
- 0.71.0 新增：Zivot-Andrews 结构突变单位根、精确两样本泊松率检验两个推断算子；核心层不变；
- 0.72.0 新增：Theil 不确定系数、标准化 DFBETAS、COVRATIO 三个关联/回归影响算子；核心层不变；
- 0.73.0 新增：Phillips-Perron 单位根、DF-GLS 单位根、Engle ARCH LM 波动检验三个时间序列诊断算子；核心层不变；
- 0.74.0 新增：CUSUM 与 EWMA 个体测量控制图两个统计过程控制算子；核心层不变；
- 0.75.0 新增：对应分析（CA）与 Tobit 左删失回归两个多元/受限因变量算子；核心层不变；
- 0.76.0 新增：GARCH 波动率模型与向量自回归（VAR）两个时间序列算子；核心层不变；
- 0.77.0 新增：t 检验、两比例检验与单因素 ANOVA 的功效/样本量计算；核心层不变；
- 0.84.0 重构：算子分类收敛为 6 类（Data/Statistics/Machine Learning/Omics/Visualization/Quality Control）；算子/Reader 元数据、功能预览、平台标记与 catalog integrity 测试；修正 Reader 发现去重；核心执行层不变；
- 0.97.0：新增高斯过程回归（gaussian_process_regressor），固定 RBF 核与观测噪声，不做边际似然优化；输出观测/拟合/残差/后验标准误；闭式 GP 公式手算对照；核心层不变；
- 0.96.0：新增向量误差修正模型（vecm），复用 Johansen trace/eigen 诊断与 statsmodels VECM，输出协整向量 beta 与调整速度 alpha；R `urca::ca.jo` 对照；核心层不变；
- 0.95.0：新增 B 样条回归（spline_regression），`patsy.bs` 三次 B 样条基 + OLS，输出拟合/残差/均值标准误/置信区间；R `splines::bs` 对照；核心层不变；
- 0.94.0：新增 Box-Cox 变换（box_cox），逐特征 MLE 估计 lambda，支持固定 lambda、shift 与缺失值保留；R `MASS::boxcox` 对照；核心层不变；
- 0.93.0：新增概率单位回归（probit_regression），用 statsmodels GLM 的 probit link 拟合二分类响应；输出系数/标准误/z/p/置信区间并记录 pseudo-R²；R `glm(family=binomial(link="probit"))` 逐值对照；核心层不变；
- 0.92.0：新增季节性 ARIMA（sarima），在 ARIMA 基础上支持 `(P,D,Q,s)` 季节阶数；输出系数/标准误/z/p/置信区间与 sigma2、loglik、AIC/BIC；R `stats::arima` 季节模型逐值对照；核心层不变；
- 0.91.0：新增非度量多维尺度分析（nmds），SMACOF + classical-MDS 确定性起点，输出坐标与 Kruskal stress；仅做定性/阈值对照，不声明与 R `MASS::isoMDS` 逐值一致；核心层不变；
- 0.90.0：新增 Fine-Gray 竞争风险回归（fine_gray），加权子分布风险部分似然 + 稳健 sandwich 协方差；R `cmprsk::crr` 对照；核心层不变；
- 0.89.0：新增 Bai-Perron 多结构突变回归（bai_perron）；用动态规划最小化分段残差平方和，R `strucchange::breakpoints` 对照；核心层不变；
- 0.88.0：新增决策曲线分析（dca）与 LOWESS 平滑（lowess）两个统计算子；项目许可证切换为 Apache-2.0；核心层不变；
- 0.87.0：新增 ARIMA(p,d,q) 时间序列模型与保序回归（isotonic）两个统计算子；ARIMA 的协方差用 `cov_type="approx"` 对齐 R Hessian SE；核心层不变；
- 0.86.0：新增 Chao1 与个体稀疏化（rarefaction）两个多样性算子；核心层不变；
- 0.85.0：新增 Weibull AFT 生存回归与精确 Hardy-Weinberg 检验；补充 9 个系统对象参考页（Form/Task/Graph/Project/Reader/Step/Runner/Registry/SDK）；未改核心执行层；
- 0.83.0 新增：距离基冗余分析（db-RDA）与留一研究 Meta 分析两个多元/证据综合算子；核心层不变；
- 0.82.0 新增：主坐标分析（PCoA）与典范对应分析（CCA）两个非约束/约束排序算子；核心层不变；
- 0.81.0 新增：逆高斯回归、beta 离散度齐性检验、零膨胀负二项回归三个回归/多元算子；核心层不变；
- 0.80.0 新增：GSEA `.rnk` 排名列表、`.cls`/`.grp` 表型标签三个 Reader；核心层不变；
- 0.79.0 新增：逆方差固定/随机效应 Meta 回归（moderator 回归）一个证据综合算子；核心层不变；
- 0.78.0 新增：Beta 回归与冗余分析（RDA）两个回归/约束排序算子；核心层不变；
- 0.65.0 新增：方差比检验、Youden 指数、Krippendorff α 三个推断/一致性算子；核心层不变；
- 0.58.0 新增：轮廓系数、调整兰德指数、归一化互信息三个聚类验证/一致性算子；核心层不变；
- 0.57.0 新增：Tukey HSD、Tamhane T2、Student-Newman-Keuls 三个全成对均值比较算子；核心层不变；
- 0.56.0 新增：Chacko 有序备择、Fligner-Wolfe 对照比较、Mack-Wolfe 伞形检验三个算子；核心层不变；
- 0.55.0 新增：Anscombe-Glynn 峰度、Bonett-Seier 峰度、Mauchly 球形三个算子；核心层不变；
- 0.51.0 新增：Fligner-Killeen、Mood 尺度检验、Siegel-Tukey 秩离散度检验三个算子；核心层不变；
- 0.50.0 新增：Levene 方差齐性、Brown-Forsythe 稳健方差齐性、Barnard 精确独立性检验三个算子；核心层不变；
- 0.49.0 新增：Durbin 平衡不完全区组检验、Skillings-Mack 缺失区组检验、Cuzick 有序趋势检验三个算子；核心层不变；
- 0.42.0 新增：Shapiro-Wilk 正态性检验、Lilliefors 正态性检验、Moses 极端反应检验三个算子；核心层不变；
- 0.41.0 新增：Bhapkar 边际齐性检验、Von Neumann 随机性检验、Shapiro-Francia 正态性检验三个算子；核心层不变；
- 0.40.0 新增：Van der Waerden 正态得分检验、Bartels 秩检验、Woolf 同质 OR 检验三个非参数/随机性算子；核心层不变；
- 0.39.0 新增：Hotelling's T²、Yuen 截尾均值 t 检验、列联表 G 检验三个多元/稳健/分类数据检验算子；核心层不变；
- 0.38.0 新增：Somers' D、Goodman-Kruskal gamma、Kendall's W 三个有序关联/一致性算子；核心层不变；
- 0.17.0 新增：Holm/BY 校正、Cohen's d/Hedges g、Cliff's delta、η²、rank-biserial、Davies–Bouldin、Calinski–Harabasz、ARI、混淆矩阵、ROC 曲线、Mann–Kendall；BLAST tabular/HMMER tblout/InterProScan/EMBL/HMM/MOL2/SMI/bedMethyl Reader；核心层不变；
- 0.13.0 新增：KS 两样本、Brunner-Munzel、Fligner-Killeen、置换检验、符号检验、Jarque-Bera；核心层不变；
- 原生 Windows 缺 `pysam`/`pyBigWig`：BAM/CRAM/BCF/BigWig 需 WSL/Linux；见 [Windows 兼容性](windows_compatibility.md)；
- 尚未支持：原始峰列表解析、空间转录组、影像等；
- 大矩阵：heatmap 有 `max_cells/max_pixels` 保护；H5AD/10x full 模式仍可能 densify。

## 8. 扩展方向

优先按**数据家族 + 科学问题**扩展，而不是按后缀堆叠：

0.8.0 已完成第一批：GMT/Loom/BIOM、GSEA/ORA、doublet/pseudobulk/marker score、meta/PRS、rollup/moderated t、ANCOM/ALDEx 风格差异丰度。

下一批：
1. **基础格式**：BAM/CRAM、BigWig/BigBed、narrowPeak/BEDPE；
2. **核心算子**：TMM/RLE/voom、GSEA 的 fgsea 对照、ambient RNA；
3. **单细胞/空间**：Leiden、轨迹、Visium；
4. **蛋白/代谢**：MSstats 对照、峰列表细节（mzML/mzXML/mzTab 已支持摘要）；
5. **遗传**：fine-mapping、VEP 注释；
6. **专用格式**：h5Seurat、GenBank/Newick/PDB、影像。

每个新增必须走 RFC、契约、独立 oracle、公开数据、文档、注册表和全量回归；详见 [protocol_suite.md](protocol_suite.md) 与 [sop_matrix.md](sop_matrix.md)。

## 9. 进一步阅读

- [协议总集](protocol_suite.md)
- [参考索引](reference/README.md)
- [任务 SOP](route_sop.md)
- [LLM 手册](llm_guide.md)
- [用户手册](user_guide.md)
- [测试矩阵](sop_matrix.md)
- [更新记录](changelog.md)
