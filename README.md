# BioPipe

BioPipe 是本地生信流水线引擎 + Studio 可视化工作区 + CLI/MCP Agent 接口。它用
Reader 读取标准格式，用带类型契约的算子处理 `Form`，并在本地生成表格、图片和报告。
BioPipe 本身不提供 AI 服务。

当前源码版本 **0.104.0**：**402 个算子、85 个 Reader、6 个 provider 包、21 条路线**。

0.84 起算子分类归一为 6 类；每个算子与 Reader 都有功能预览，平台受限格式在界面和 manifest 中标记。

0.86 新增 Chao1 与 rarefaction（个体稀疏化）两个微生物/生态多样性算子；0.87 新增 ARIMA 与保序回归（isotonic）两个统计算子；0.88 新增决策曲线分析（DCA）与 LOWESS 平滑，并将项目许可证切换为 Apache-2.0；0.89 新增 Bai-Perron 多结构突变回归；0.90 新增 Fine-Gray 竞争风险回归；0.91 新增非度量多维尺度分析（NMDS）；0.92 新增季节性 ARIMA（SARIMA）；0.93 新增概率单位回归（probit regression）；0.94 新增 Box-Cox 变换（box_cox，逐特征 MLE）；0.95 新增 B 样条回归（spline_regression，三次 B 样条基）；0.96 新增向量误差修正模型（vecm，VECM）；0.97 新增高斯过程回归（gaussian_process_regressor，固定 RBF 核与闭式后验）；0.98 新增可加 B 样条回归（additive_spline_regression，多个自变量的三次 B 样条可加模型）；0.99 新增环境向量拟合（envfit，线性环境向量与 R²）；0.100 新增可加 B 样条 GLM（additive_glm，binomial/poisson 族）。0.101 新增区间删失 Weibull AFT 回归（interval_censored_regression，区间/右删失/左删失/精确时间）。0.102 新增条件 logistic 回归（conditional_logistic，匹配病例对照分层）。0.103 新增层次聚类（hierarchical_clustering，single/complete/average/Ward.D2）。0.104 新增两条基于公开数据的路线组合示例（UCI 乳腺癌差异分析 + 随机森林分类；NCCTG 肺癌年龄回归 + 生存分析），不新增算子。

## 价值主张

**一个巨大、可维护、经过验证的工具集，让 agent 以最低成本调用分析，而不必自己写代码——从而避免生成实现时的逻辑错误和额外 token 消耗。**

- 契约化算子库：注册表 + 两层测试 + 文档索引，agent 在边界内选算子，不靠猜。
- 算子/Reader/ML 模型统一为一等公民：模型即插件，同一套发现、校验、组合、追溯机制。
- 可视化可追溯：每步绑定契约与注册表，不只是画布。
- 底层稳定：合规算子组合行为可预测。
- 边际成本趋零：dsh 批量生成、测试筛真伪，工具集能快速扩大。

**差异化：别人让 agent 现写分析代码，BioPipe 让 agent 调用已验证的工具集。**

完整说明见 [价值主张与设计原则](docs/vision.md)。

## 先读文档

完整入口：[docs/README.md](docs/README.md)。

最值得先读的六份：

| 文档 | 作用 |
|---|---|
| [架构总览](docs/architecture.md) | 仓库结构、执行流、模块边界、改哪里 |
| [协议总集](docs/protocol_suite.md) | Form/Reader/算子/契约/注册表/扩展/测试规范 |
| [参考索引](docs/reference/README.md) | 每个 Reader/算子的参数、契约、源码/测试链接 |
| [系统对象](docs/reference/subjects/README.md) | 九个核心对象：Form/Task/Graph/Project/Reader/Step/Runner/Registry/SDK |
| [覆盖审计](docs/coverage_audit.md) | 402 算子/85 Reader 的覆盖、核心创新点落实度与缺口 |
| [路线组合示例](examples/route_combinations/README.md) | 两条可直接运行的组合路线及逐步解释 |
| [任务 SOP](docs/route_sop.md) | 从数据到自定义路线、`--check`、运行和结果解释 |

按角色阅读：

- 用户：[用户手册](docs/user_guide.md) → [任务 SOP](docs/route_sop.md) → [LLM 手册](docs/llm_guide.md)
- LLM/Agent：[架构总览](docs/architecture.md) → [LLM 手册](docs/llm_guide.md) → `docs/reference/*_index.json`
- 开发者：[架构总览](docs/architecture.md) → [协议总集](docs/protocol_suite.md) → [SDK](docs/sdk_quickstart.md)

## 快速开始（源码）

需要 Python 3.11+、Node 22.12+。

```bash
python -m venv .venv
# 按 shell 的方式激活 .venv
python -m pip install -e ".[agent,dev]"

cd frontend
npm install
npm run build
cd ..

python scripts/studio.py
```

打开 `http://127.0.0.1:8765`。前端/桌面的详细配置见
[安装](docs/installation.md)、[桌面](docs/desktop.md)、[迁移](docs/portability.md)。

也可以直接跑任务：

```bash
python scripts/run.py tasks/sop_demo --check
python scripts/run.py tasks/sop_demo
```

## 常用命令

```bash
python -m pytest -q                              # 全量测试
python -m pytest -q tests/sop                    # 独立 SOP
python -m biopipe inspect "<文件绝对路径>" --json   # 数据概况
python scripts/run.py tasks/<任务> --check         # 静态预检
python scripts/build_reference_docs.py --check    # 文档完整性
python -m biopipe registry check                  # 注册表
```

## 仓库地图

```text
src/core/          Form、契约、错误、数值精度
src/reader/        Reader 路由与格式解析
src/task/          manifest、Context、Runner、Step、内存/资源
src/web/           FastAPI、Graph、路线、任务、资产
frontend/          React Studio
biopipe/           CLI、注册表、包、插件、inspect
biopipe_sdk/       公开扩展 SDK
desktop/           WinForms/WebView2 宿主
scripts/           run/studio/registry/文档生成
tasks/             示例任务与自定义任务
routes/            可复用路线模板
tests/             单元、契约、SOP、路线
docs/reference/    自动生成 Reader/算子参考页
```

更细的模块职责和“改 X 看哪里”见 [架构总览](docs/architecture.md)。

## 扩展与 Agent

- 新 Reader/算子只依赖 `biopipe_sdk`，声明严格 schema/contracts。
- 单文件 drop-in、wheel、route 三条扩展路径；依赖隔离和 pin 见
  [插件生命周期](docs/plugins.md)。
- Agent 通过 CLI/MCP 读取上下文、提交 revision-checked 编辑；运行需要显式权限。
  见 [Agent API](docs/agent_api.md)。
- 扩展前先读 [协议总集](docs/protocol_suite.md) 和 [测试矩阵](docs/sop_matrix.md)。
  没有独立 oracle 的算子不标 stable。

## 当前边界

- 已覆盖：CSV/TSV/TXT/Parquet、Excel、BED/GFF3/GTF/GAF、FASTA/FASTQ、MTX、H5AD/10x H5、
  VCF/BCF、PLINK1/2、BGEN、GMT/Loom/BIOM、HDF5/Zarr、SAM/PAF/BEDPE、
  Clustal/NEXUS/Newick/Phylip/Stockholm、GenBank/PDB、PED/GFA、MAF/chain、BigWig、
  mzML/mzXML/mzTab、mzIdentML/pepXML/mzDATA/protXML 摘要、FCS/AB1。
- 流式细胞术：FCS 事件矩阵 + arcsinh 变换 + 矩形门控 + 溢漏补偿。
- 配对 ROC：DeLong 配对检验，要求同一样本、较高分数为阳性；Cochran Q：宽表二分类、完整样本。
- 回归诊断：Breusch-Godfrey、RESET、Harvey-Collier 与既有 White/Chow/Ljung-Box 并存。
- 回归模型：多项 logit、条件 logit、Huber 稳健回归、Gamma 回归、零膨胀 Poisson。
- 一致性/可靠性：ICC（组内相关）、Lin's CCC（一致性相关系数）。
- 方法学一致性：Passing-Bablok 与 Deming 回归（仅点估计，不提供 CI）。
- 可靠性与多变量：Cronbach's alpha、典型相关（canonical correlation）、Wald–Wolfowitz runs test。
- 因子可分析性：KMO 取样适切性、Bartlett 球形检验。
- 效应量与有序趋势：Cramér's V、Jonckheere-Terpstra 有序秩检验、varimax 正交旋转。
- 趋势/离群/正态性：Cox-Stuart 趋势、Grubbs 单离群值、Anderson-Darling 正态性检验。
- 精确/中位数：二项精确检验、Mood 中位数检验、Boschloo 精确检验。
- 方差齐性/精确独立性：Levene 方差齐性、Brown-Forsythe 稳健方差齐性、Barnard 精确检验。
- 尺度/离散度：Fligner-Killeen、Mood 尺度检验、Siegel-Tukey 秩离散度检验。
- 偏度/拟合优度/方差离群：D'Agostino 偏度检验、Pearson χ² 拟合优度、Cochran C 方差离群检验。
- 秩尺度/离群/校准：Ansari-Bradley 秩尺度、χ² 方差离群、分箱校准曲线。
- 回归诊断：Goldfeld-Quandt 异方差、Rainbow 线性偏离。
- 回归影响/残差诊断：OLS 杠杆值、Cook 距离、DFFITS；标准化残差、学生化残差、PRESS。
- 峰度/球形：Anscombe-Glynn 峰度、Bonett-Seier 峰度、Mauchly 球形检验。
- 有序备择/伞形：Chacko 有序备择、Fligner-Wolfe 对照组比较、Mack-Wolfe 伞形检验。
- 稳健/多元：Sen 斜率、Mahalanobis 距离、Box's M 协方差齐性。
- 事后比较/变点：Scheffe、Nemenyi、Pettitt 变点检验。
- 非参数/随机性：Van der Waerden 正态得分检验、Bartels 秩检验、Woolf 同质 OR 检验。
- 边际齐性/随机性/正态性：Bhapkar 检验、Von Neumann 随机性、Shapiro-Francia 正态性。
- 正态性/极端反应：Shapiro-Wilk 正态性、Lilliefors 正态性、Moses 极端反应检验。
- 有序备择/多元正态/序列随机：Page 有序备择、Mardia 多元正态、Turning Point 序列随机性检验。
- 多元/稳健检验：Hotelling's T²、Yuen 截尾均值 t 检验、列联表 G 检验。
- 全成对均值比较：Tukey HSD、Tamhane T2、Student-Newman-Keuls。
- 时间序列/列联表/聚类一致性：Box-Pierce、Stuart-Maxwell、变异信息。
- 自相关/部分自相关/PR 曲线：ACF、PACF、precision-recall 曲线。
- 聚类一致性：Fowlkes-Mallows、同质/完整/V-measure、成对混淆矩阵。
- 时间序列诊断：互相关函数、BDS 非线性依赖、差分符号检验。
- 时间序列单位根/波动：Phillips-Perron、DF-GLS、Engle ARCH LM。
- 时间序列波动/向量自回归：GARCH、VAR。
- 功效/样本量：t 检验、两比例、单因素 ANOVA 的 achieved power。
- 比例/成分数据与排序：Beta 回归、冗余分析（RDA）、主坐标分析（PCoA）、典范对应分析（CCA）。
- 流行病学效应量：风险比、比值比、Cohen's h（2×2 表，log/Wald 置信区间）。
- 评分者一致性：Gwet AC1、Brennan-Prediger、Conger kappa（未加权，容忍缺失评分）。
- GSEA 输入：`.rnk` 排名列表、`.cls`/`.grp` 表型标签；保留类别编码供分组算子直接使用。
- 有序关联：Somers' D、Goodman-Kruskal gamma、Kendall's W。
- 竞争风险：Fine-Gray 子分布风险回归（fine_gray），输出系数、HR、稳健 SE、CI 与事件/竞争/删失计数；R `cmprsk::crr` 对照。
- 原生 Windows 缺 `pysam`/`pyBigWig`：BAM/CRAM/BCF/BigWig 请用 WSL/Linux；见
  [Windows 兼容性](docs/windows_compatibility.md)。
- 尚未覆盖：原始峰列表、空间转录组、影像。
- 大矩阵/内存：heatmap 有 `max_cells`/`max_pixels` 保护；H5AD/10x full 模式仍可能 densify。
- 21 条 route 均有仓库内 fixture，pytest 会实际执行；真实数据 demo 另行覆盖。

## 版本与更新记录

- 当前：**0.104.0**，见 [CHANGELOG](docs/changelog.md)。
- Windows 测试环境快照：[conda](windows-biopipe-conda.yml) /
  [pip](windows-biopipe-pip-freeze.txt)。

## 许可证

本项目采用 **Apache License 2.0** 开源许可证。完整许可证文本见
[LICENSE](LICENSE)，版权与归属声明见 [NOTICE](NOTICE)。

Copyright 2026 Haojian Li

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
