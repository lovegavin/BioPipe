# BioPipe 覆盖与核心创新点审计（0.84–0.106）

本页回答两个问题：**当前算子和 Reader 覆盖到什么程度**，以及**这些扩展是否真的在支撑 BioPipe 的核心创新点**，而不只是增加数量。

审计基线：`0.84.0` 全量快照；0.85 新增 `aft`/`hardy_weinberg`，0.86 新增 `chao1`/`rarefaction`，0.87 新增 `arima`/`isotonic`，0.88 新增 `dca`/`lowess`，0.89 新增 `bai_perron`，0.90 新增 `fine_gray`，0.91 新增 `nmds`，0.92 新增 `sarima`，0.93 新增 `probit_regression`，0.94 新增 `box_cox`，0.95 新增 `spline_regression`，0.96 新增 `vecm`，0.97 新增 `gaussian_process_regressor`，0.98 新增 `additive_spline_regression`，0.99 新增 `envfit`，0.100 新增 `additive_glm`，0.101 新增 `interval_censored_regression`，0.102 新增 `conditional_logistic`，0.103 新增 `hierarchical_clustering`；0.104 新增两条路线组合示例；0.105 新增第三条公开数据路线组合示例（vegan::mite 泥炭沼泽甲螨）；0.106 新增第四条公开数据路线组合示例（scikit-learn diabetes：分类 + 回归 + PCA）但不改变算子/Reader/路线计数，当前 **402 个算子 / 85 个 Reader / 21 条路线 / 6 个包**，注册表 `errors []`。前端按 Vitest 实际用例统计为 **39 tests / 9 files**，构建通过。下文的分类/覆盖证据以 0.84 快照为主，0.85–0.106 增量证据见 SOP §85–§106。本文只记录可核对的事实；没有把“有测试”写成“每个算子都有独立外部 oracle”。

> 计数口径修正：0.83 审计曾沿用历史累计数写作“前端 325 passed”。0.84 起前端只按 `npm test -- --run` 的实际 Vitest 用例数记录；历史 changelog 中的累计口径不再作为本文证据。

## 1. 数量与增长

| 指标 | 0.18.0 | 0.83.0 | 0.84.0 | 0.85.0 | 0.86.0 | 0.87.0 | 0.88.0 | 0.89.0 | 0.90.0 | 0.91.0 | 0.92.0 | 0.93.0 | 0.94.0 | 0.95.0 | 0.96.0 | 0.97.0 | 0.98.0 | 0.99.0 | 0.100.0 | 0.101.0 | 0.102.0 | 0.103.0 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 算子 | 193 | 379 | **379** | **381** | **383** | **385** | **387** | **388** | **389** | **390** | **391** | **392** | **393** | **394** | **395** | **396** | **397** | **398** | **399** | **400** | **401** | **402** |
| Reader | 73 | 85 | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** | **85** |
| 路线 | 21 | 21 | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** | **21** |
| 包 | 6 | 6 | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** | **6** |

- 0.18→0.83 共 65 个版本，平均每版约 **2.9 个算子**；0.84 本轮不新增算子/Reader，集中偿还可发现性债务。
- 算子增长远快于 Reader：0.18→0.83 算子增加 186，Reader 只增加 12。大量新算子依赖通用表，专门格式仍集中在 85 个 Reader 中。
- 0.84 的分类、预览、Reader 元数据、平台标记与自动完整性检查，是为后续扩张降低边际成本，不是数量扩张。
- 0.86 新增 `chao1` 与 `rarefaction` 两个多样性算子；0.87 新增 `arima` 与 `isotonic` 两个统计算子；0.88 新增 `dca` 与 `lowess` 两个统计算子，并将许可证切换为 Apache-2.0；0.89 新增 `bai_perron` 一个结构突变算子；0.90 新增 `fine_gray` 一个竞争风险算子；0.91 新增 `nmds` 一个排序算子；0.92 新增 `sarima` 一个时间序列算子；0.93 新增 `probit_regression` 一个二分类回归算子；0.94 新增 `box_cox` 一个数据变换算子；0.95 新增 `spline_regression` 一个可解释非线性回归算子；0.96 新增 `vecm` 一个多变量协整/误差修正算子；0.97 新增 `gaussian_process_regressor` 一个固定核高斯过程回归算子；0.98 新增 `additive_spline_regression` 一个可加 B 样条回归算子；Reader 数不变，分类仍为 6 类。 0.99 新增 `envfit` 一个环境向量拟合算子；0.100 新增 `additive_glm` 一个可加 B 样条 GLM 算子；0.101 新增 `interval_censored_regression` 一个区间删失 Weibull AFT 算子；0.102 新增 `conditional_logistic` 一个条件 logistic 算子；0.103 新增 `hierarchical_clustering` 一个层次聚类算子；0.104–0.106 新增路线组合示例，不改变算子/Reader/路线计数；Reader 数不变，分类仍为 6 类。

## 2. 算子分类与可发现性

### 2.1 归一后的分类

0.84 把注册表里的 18 种原始写法收敛为 **6 个英文首字母大写类别**：

| category | 算子数 |
|---|---:|
| Data | 36 |
| Statistics | 237 |
| Machine Learning | 62 |
| Omics | 45 |
| Visualization | 14 |
| Quality Control | 8 |

- 归一发生在 `build_catalog` **之后**，避免 `describe_operator` 从 `Step.category` 覆盖分类；注册表保存归一后的机器分类。
- 前端只做显示映射；未知自定义插件类别回退为 `Other`，不污染内置 6 类。
- 0.83 的 `Analysis` + `analysis` 共 189 个“大杂烩”已拆入 Statistics/Machine Learning/Omics/Data 等可导航类别。
- 仍有分类债：Reader 目前全部归为 `Data`，还没有按格式族细分；这留到 Reader 增长时处理。

### 2.2 功能预览

- 402 个算子的 `description` **全部非空**；缺描述的算子由 `title + 输入数 + 输出类型` 生成回退文案，不再出现空白卡片。
- 85 个 Reader 的 `title/category/description/extensions/platforms` 全部进入 SDK `Descriptor` 和前端 `ReaderSpec`；Reader 首次有独立库区。
- 算子库卡片显示两行功能摘要；Inspector 显示“功能预览”（描述、输入数、输出名/报告），源节点显示 Reader 描述、扩展名与平台限制。
- 图标不是本轮要求：`operatorPresentation.ts` 仍有 281 个显式图标/预览条目，部分算子回退到类别图标；功能预览本身已由注册表动态补齐，不依赖显式条目。

## 3. 前端同步与自动检查

- 前端 `presentCatalog` 同时映射 **operators 和 readers**；算子/Reader 的数量、搜索、空状态、分组都包含 Reader。
- 新增 `tests/test_catalog_integrity.py`：把 `builtin_packages.json` 与 `discover_steps()`/`discover_readers()` 的实际源码集合对比，检查 ID、category、title、description、extensions，防止新模块只写源码却漏进注册表。
- 前端测试加载同一份 manifest，强制：
  - 所有算子与 Reader 都有非空 title/description；
  - 所有 category 属于 6 类（`Other` 只允许未知插件）；
  - 4 个平台受限 Reader 正确标记；
  - Reader 卡片渲染，且无中文分组硬编码。
- 修复 Reader 发现重复：`tenx_h5_reader.py` 导入的 `CsvReader` 曾被计入 Reader 集合；现在只接受定义在当前模块的类。
- 修复 `youden_index.py` 的 UTF-8 BOM；BOM 会让注册表静态 `ast.parse` 直接失败。

## 4. Reader 覆盖

85 个 Reader 覆盖的主要格式族：

- **通用表格**：CSV、TSV、TXT、Excel、JSON、Parquet、HDF5、NPZ、Zarr。
- **基因组区间/轨道**：BED、BEDPE、BEDGRAPH、BEDMETHYL、BroadPeak、NarrowPeak、GFF/GFF3/GTF、WIG、BigWig、FAI、Cytoband。
- **序列/比对**：FASTA、FASTQ、SAM、BAM、CRAM、PAF、BLAST tabular、PSL、Chain、GFA。
- **变异/遗传**：VCF、BCF、BGEN、PLINK1/2、PED、MAP、FAM、BIM、HapMap、MAF。
- **单细胞/表达**：H5AD、10x H5、Loom、MTX、GCT、BIOM。
- **系统发生**：Newick、Nexus、Phylip、Stockholm、Clustal。
- **结构/化学**：PDB、mmCIF、MOL、MOL2、SDF、SMI、XYZ、GRO。
- **质谱**：MGF、mzML、mzXML、mzData、mzTab、mzIdentML、pepXML、protXML。
- **流式/测序痕迹**：FCS、AB1。
- **注释/基因集**：GAF、OBO、InterProScan、HMM、HMMER tblout/domtblout、GMT、RNK、CLS、GRP。
- **核酸记录**：EMBL、GenBank。

平台标记：`BamReader` / `CramReader` / `BcfReader` / `BigWigReader` 标记 `platforms: [linux, darwin]`，前端显示“Windows 不可用”；它们依赖 `pysam`/`pyBigWig`，原生 Windows 环境不保证可用。其余 Reader 不声明平台限制。

覆盖缺口：

1. **空间/影像/单细胞 ATAC 仍缺**：Visium/Xenium/CosMx、OME-TIFF、fragments 等没有专门 Reader；通用矩阵 Reader 不能替代坐标与 barcode 语义。
2. **Reader 数量落后算子 4.5 倍**：379/85；很多算子只能吃通用表，专门格式的“最后一公里”仍要用户预处理。
3. **Reader 权威对照以黄金文件为主**：格式 Reader 多数用固定样例 + 负例测试，不是每个都有外部解析器 oracle。这是合理边界，但文档不能写成“全部与权威实现逐项对齐”。

## 5. 五个核心创新点逐项审计

判断标准来自 `docs/vision.md`：可发现、可校验、可组合、可追溯、可维护，而不是数量本身。

| 支撑手段 | 状态 | 0.84 证据 | 主要缺口 |
|---|---|---|------:|
| 1. 契约化算子库 | **基本落实** | 379 个算子统一 schema/contracts/注册表/参考页；6 类归一；catalog integrity 测试；算子/Reader 描述全覆盖 | 不是 379 个算子都有外部 oracle；Reader 分类仍粗 |
| 2. 算子/Reader/ML 模型统一为一等公民 | **部分落实** | 算子与 Reader 都走 `Descriptor`/注册表/前端 manifest；Reader 元数据与平台标记进入 SDK | 本轮没有新增 ML 模型，模型即插件仍主要是架构声明；Reader 与算子的生命周期仍未完全同构 |
| 3. 可视化可追溯 | **部分落实** | 前端算子库 + Reader 库 + Inspector 功能预览；所有条目有描述/输入输出/平台信息 | 图标未全覆盖；从 Studio 节点跳到参考页、源码、测试证据的端到端闭环仍未实现 |
| 4. 底层稳定 | **基本落实** | 本轮改元数据/目录/前端，并修正 Reader 发现去重、wheel 描述符比较与 registry/source scan 归一开关；未改 runner、Step 基类或数学实现 | 全量测试结果见下；注册表/Reader 发现层有改动，不能声称“零核心改动” |
| 5. 边际成本趋零 | **落实但有质量债** | 新算子/Reader 可由统一注册表与自动检查发现；描述/分类不再逐条手填 | Reader 覆盖落后；分类/预览已补，但证据台账、图标、文档链接仍需持续治理 |

### 结论

**0.84 补上了 0.83 审计里最影响可发现性的两块：分类归一化和功能预览；但没有把五个支撑全部做完。**

- 最强的是 **1（契约化）**、**4（底层稳定）**：算子/Reader 的注册、描述、分类、平台标记现在有自动检查。
- **2（统一插件）** 仍是部分落实：Reader 元数据统一了，但本轮没有新的 ML 模型证据。
- **3（可视化可追溯）** 仍是部分落实：功能预览已覆盖，但“节点 → 算子页 → 源码/测试”的闭环还没接上。
- **5（边际成本）** 的“加一个算子/Reader 能被自动发现”已经成立；Reader 覆盖和外部 oracle 台账仍是质量债。

## 6. 复现与证据

在项目根目录运行：

```bash
python -m biopipe registry check
python -m pytest -q -rs
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

- `registry check` 应输出 398 operators / 85 readers / 6 packages / errors []。
- 0.84 分类/目录定向测试：`tests/test_catalog_integrity.py`、`tests/test_operator_metadata.py`、`tests/test_registry_maintenance.py`、`tests/test_reference_docs.py`，共 20 passed。
- 前端：39 passed（9 files），构建通过。
- 全量 pytest：**974 passed, 1 skipped**。

## 7. 0.99 增量证据

- `envfit`：R `vegan::envfit(permutations=0)` 的 n=30 fixture 中，三个环境变量的 R² 为 **0.8558 / 0.7321 / 0.0225**，单位化方向与 R 的 `arrows` 一致（atol 1e-5）。
- 证据：`tests/test_envfit.py` 3 项 + `tests/test_r_oracles79.py` 1 项 = **4 passed**；增量门 **20 passed**；`-W error` **6 passed**；frontend **39 passed / 9 files**；registry **398/85/21/6**。
- 边界：`permutations=0`，因此没有置换 p 值；方向是线性梯度，不是非线性环境曲面。

相关文档：[价值主张与设计原则](vision.md) · [参考索引](reference/README.md) · [协议总集](protocol_suite.md) · [SOP 矩阵](sop_matrix.md) · [Oracle 矩阵](oracle_matrix.md)。
