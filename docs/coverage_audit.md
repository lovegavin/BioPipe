# BioPipe 覆盖与核心创新点审计（0.83.0）

本页回答两个问题：**0.83 时算子和 Reader 覆盖到什么程度**，以及**这些扩展是否真的在支撑 BioPipe 的核心创新点**，而不只是增加数量。

审计基线：`0.83.0`，注册表 **379 个算子 / 85 个 Reader / 21 条路线 / 6 个包**，注册表 `errors []`。前端测试 **325 passed**。本文只记录可核对的事实；没有把“有测试”写成“每个算子都有独立外部 oracle”。

## 1. 数量与增长

| 指标 | 0.18.0 | 0.83.0 | 变化 |
|---|---:|---:|---:|
| 算子 | 193 | 379 | **+186** |
| Reader | 73 | 85 | **+12** |
| 路线 | 21 | 21 | 0 |
| 包 | 6 | 6 | 0 |

- 0.18→0.83 共 65 个版本，平均每版约 **2.9 个算子**。
- 算子增长远快于 Reader：算子增加 186，Reader 只增加 12。大量新算子依赖通用表（CSV/TSV/矩阵），但专门格式仍集中在 85 个 Reader 中。
- 0.83 本批新增 2 个算子（`dbrda`、`leave_one_out`），定向测试 9 个；官方增量门 **25 passed**，`-W error` **11 passed**。
- 全量测试基线仍是 0.18 的 **606 passed / 1 skipped**；0.83 没有做全量 pytest，因此不能声称全量回归覆盖了 0.83。

## 2. 算子覆盖

### 2.1 按包

| 包 | 算子数 |
|---|---:|
| `biopipe-core` | 329 |
| `biopipe-genetics` | 12 |
| `biopipe-expression` | 12 |
| `biopipe-plots` | 12 |
| `biopipe-microbiome` | 11 |
| `biopipe-readers` | 3 |

包分布说明：**核心包承载了绝大多数算子**，遗传/表达/绘图/微生物包是薄封装，不是独立能力域。按包统计不能替代按功能统计。

### 2.2 按注册表 `category`

| 原始 category | 数量 |
|---|---:|
| `Analysis` | 148 |
| `Statistics` | 114 |
| `analysis` | 41 |
| `数据整理` | 11 |
| `Microbiome` | 11 |
| `可视化` | 10 |
| `data` | 6 |
| `Survival` | 5 |
| `Sequence` | 5 |
| `统计分析` | 5 |
| `Genetics` | 5 |
| `Single cell` | 4 |
| `质量控制` | 4 |
| `Data preparation` | 3 |
| `Visualization` | 3 |
| `Proteomics` | 2 |
| `visualization` | 1 |
| `quality_control` | 1 |

这张表暴露了一个**可发现性债务**：

- 18 种写法里存在大小写、单复数、中英文混用（`Statistics` / `统计分析`、`Visualization` / `可视化`、`Analysis` / `analysis`）。
- `Analysis` + `analysis` 共 **189 个算子**，接近总量一半，却不是一个可导航的功能分类；它把统计、整理、转换、QC 等混在一起。
- 前端主要归并为质量控制 / 统计分析 / 数据整理 / 可视化（另有未分类、微生物组等回退），并靠 `operatorPresentation.ts` 做映射。也就是说：**注册表的 category 与用户看到的分类不是同一套语义**。
- `operatorPresentation.ts` 目前只有 **281 个显式算子条目**；379 个算子中约 **98 个没有显式图标/预览**，会回退到 registry 分类和空图标。前端 325 个测试通过，但没有强制“每个算子必须有图标/预览”的全覆盖测试。
- 这不会让算子算错，但会让 agent 和用户更难“先筛候选，再读页面”，直接削弱核心创新点里的“可发现”。

### 2.3 功能覆盖（按能力，不按 category）

当前覆盖面已经跨过“只有基础统计”的阶段：

- **统计推断**：参数/非参数检验、方差分析、事后比较、等效性/优效性、功效与样本量、多重比较、meta 分析、meta 回归、leave-one-out。
- **回归与计数模型**：线性/GLM、Beta、Tobit、逆高斯、零膨胀负二项、GARCH、VAR、中介/调节、校准与风险预测。
- **多元与排序**：PCA、CA、PCoA、CCA、RDA、db-RDA、聚类与聚类一致性、距离相关、Mantel/偏 Mantel、Procrustes。
- **生存/临床**：Kaplan-Meier、Cox、RMST、竞争风险相关、诊断/校准、NRI/IDI。
- **遗传/组学**：Fst、亲缘矩阵、GWAS 相关处理、单细胞 HVG/细胞周期、表达矩阵、微生物差异与组成。
- **序列/结构/质谱/流式**：反向互补、翻译、密码子、限制性位点、蛋白性质、PDB/mmCIF、mzML/mzXML/mzTab、FCS 等。
- **可视化**：热图、火山图、PCA/排序图、控制图等（以表格化结果 + 绘图算子为主）。

这里不给出每个功能域的精确计数，因为注册表 `category` 不支持可靠拆分；强行按标题聚类会制造不可复现的数字。**分类归一化应作为 0.84 的优先事项。**

## 3. Reader 覆盖

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

覆盖缺口与风险：

1. **平台依赖型格式存在但不等于处处可用**：BAM/CRAM/BCF/BigWig 依赖 `pysam`/`pyBigWig`，原生 Windows 环境未必可装；这一点已在 Windows 兼容文档中记录。
2. **空间/影像/单细胞 ATAC 仍缺**：Visium/Xenium/CosMx、OME-TIFF、fragments 等没有专门 Reader；通用矩阵 Reader 不能替代坐标与 barcode 语义。
3. **Reader 数量落后算子 4.5 倍**：379/85；很多算子只能吃通用表，专门格式的“最后一公里”仍要用户预处理。
4. **Reader 的权威对照以黄金文件为主**：格式 Reader 多数用固定样例 + 负例测试，不是每个都有外部解析器 oracle。这是合理的，但文档不能写成“全部与权威实现逐项对齐”。

## 4. 五个核心创新点逐项审计

判断标准来自 `docs/vision.md`：可发现、可校验、可组合、可追溯、可维护，而不是数量本身。

| 支撑手段 | 状态 | 证据 | 主要缺口 |
|---|---|---|---|
| 1. 契约化算子库 | **基本落实** | 379 个算子有统一 schema/contracts/注册表/参考页；0.83 注册表 `errors []`；新算子有手算 + R oracle；生成式参考页覆盖 379/85 | 不是 379 个算子都有外部 oracle；category 语义未归一，削弱“先筛后读” |
| 2. 算子/Reader/ML 模型统一为一等公民 | **部分落实** | 新算子走 `Step`，新 Reader 走 `Reader` + 生成注册表；发现/校验/组合机制未分叉 | 0.83 没有新增 ML 模型，未用本轮证据验证“模型即插件”路径；模型与普通算子的统一性仍主要是架构声明 |
| 3. 可视化可追溯 | **部分落实** | 前端 325 tests；281/379 个算子有显式 presentation 图标/预览；画布能看到步骤与参数 | 98 个算子没有显式图标；当前证据主要是“展示层”；从 Studio 节点跳到算子页、源码、测试证据的端到端闭环未在本轮验证/新增 |
| 4. 底层稳定 | **落实** | 0.83 只新增 `src/task/step/steps/*`、测试、文档、注册表、前端展示与版本号；未改 core/Reader/Step 基类/runner | 仍是无全量 pytest 的增量验证；核心稳定性靠约束与定向测试，不是全量回归证明 |
| 5. 边际成本趋零 | **落实但有质量债** | 0.18→0.83 增加 186 算子/12 Reader；每版更新 registry/docs/frontend/version 并提交；0.83 增量门 25 | category 债务、Reader 落后、oracle 覆盖不均；数量增长快于分类/证据治理 |

### 结论

**方向是对的，但不能说五个支撑都已完整落地。**

- 最强的是 **1（契约化）** 和 **4（底层稳定）**：新增能力没有破坏核心，注册表/参考页/测试链路在持续工作。
- **5（边际成本）** 在“能快速加算子”上成立，但已经积累了两类债：分类不可导航、Reader 覆盖落后。
- **2（统一插件）** 和 **3（可视化可追溯）** 目前只能算部分落实；前者本轮没有模型侧新证据，后者仍停留在展示层。
- 因此，0.83 的准确定位是：**一个数量很大、契约较完整、但分类与证据治理需要补课的工具集**，而不是“核心创新点已经全部完成”。

## 5. 建议优先级

1. **先归一 operator category**：把 18 种写法收敛为稳定枚举；注册表存机器分类，前端只做显示映射；加一个“每个算子恰好一个分类”的测试。这是最低成本、最高收益的可发现性修复。
2. **再做 traceability 与展示补齐**：参考页已有源码/测试链接；把同一组链接接到 Studio 节点检查器，形成“节点 → 算子页 → 源码/测试”的闭环；同时补齐 98 个没有显式图标的算子，并加全覆盖测试。
3. **Reader 补缺按语义优先级**：空间转录组/影像、单细胞 ATAC fragments、原始 peak list 优先；平台依赖格式继续在 Windows 兼容文档中标注。
4. **建立 oracle 覆盖台账**：按算子记录“手算测试 / R oracle / Python oracle / 仅负例”，不要用“有测试”代替“有权威对照”。
5. **在补完 1–2 之前，控制算子扩张速度**：继续加算子会放大分类与证据债；先把“可发现、可追溯”做扎实，再恢复高速扩展。

## 6. 复现与证据

在项目根目录运行：

```bash
python -m biopipe registry check
python -m pytest tests/test_extension76.py tests/test_r_oracles66.py -q
python -m pytest tests/test_docs_links.py tests/test_reference_docs.py tests/test_portability.py -q
npm --prefix frontend test -- --run
```

- `registry check` 应输出 379 operators / 85 readers / 6 packages / errors []。
- 0.83 定向测试：7 个手算 + 2 个 R oracle = 9 passed。
- 官方增量门：25 passed；`-W error`：11 passed。
- 前端：325 passed。

相关文档：[价值主张与设计原则](vision.md) · [参考索引](reference/README.md) · [协议总集](protocol_suite.md) · [SOP 矩阵](sop_matrix.md) · [Oracle 矩阵](oracle_matrix.md)。
