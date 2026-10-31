# BioPipe 文档入口

先读这一页，再按角色选择路径。BioPipe 的文档很多，但**当前权威入口只有少数几份**；其余是专题细节、生成式参考或历史记录。

## 1. 五分钟理解仓库

1. [架构总览](architecture.md) — 模块、执行流、数据流、目录地图、改哪里。
2. [协议总集](protocol_suite.md) — Form、Reader、算子、契约、注册表、路线、扩展、测试的规范。
3. [参考索引](reference/README.md) — 387 个算子、85 个 Reader 的逐项页面和机器索引。
4. [任务 SOP](route_sop.md) — 从数据到自定义路线、验证、运行、解释结果。
5. [价值主张与设计原则](vision.md) — 为什么做、五个支撑手段、设计判断标准。
6. [覆盖与创新点审计](coverage_audit.md) — 387 算子/85 Reader 的覆盖、增长、缺口与五支撑逐项审计。
7. [系统对象](reference/subjects/README.md) — Form、Task、Graph、Project、Reader、Step、Runner、Registry、SDK 的职责、边界与不变量。

一句话：**`task.yaml`/Studio Graph → Reader → Form → Step 链 → 输出/图片/report**。Reader 负责忠实解析，算子负责数学处理，契约负责连接，测试负责证明。

## 2. 按角色的阅读路径

### 我是用户，想让 LLM 帮我搭路线

1. [用户手册](user_guide.md)
2. [任务 SOP](route_sop.md)
3. [LLM 手册](llm_guide.md)
4. [路线架构师提示词](prompts/route_architect.md)
5. 需要时查 [算子/Reader 参考](reference/README.md)

### 我是 LLM / Agent

1. [架构总览](architecture.md)
2. [LLM 手册](llm_guide.md)
3. `reference/operator_index.json` / `reference/reader_index.json`
4. 只打开候选算子的页面，再按需读源码/测试
5. 用 `python -m biopipe inspect` 和 `python scripts/run.py tasks/<dir> --check` 验证
6. 不要通读 `src/`；不要猜路径/列名/参数

### 我是开发者/专业人士

1. [架构总览](architecture.md)
2. [协议总集](protocol_suite.md)
3. [算子协议](operator_protocol.md)
4. [Reader 扩展](reader_extensions.md) / [Step 扩展](step_extensions.md)
5. [SDK 快速开始](sdk_quickstart.md) / [SDK 参考](sdk_reference.md)
6. [注册表维护](registry_maintenance.md) 与 [插件生命周期](plugins.md)
7. [测试范式](testing.md) — 严格增量 + 周期全量
8. [测试与证据矩阵](sop_matrix.md)
9. [权威实现对照矩阵](oracle_matrix.md)
10. [R oracle 设置](r_oracles.md)

### 我要新增 Reader / 算子

1. [协议总集](protocol_suite.md) 的 Reader/Operator/Testing 章节
2. [架构总览](architecture.md) 的“扩展点”和“改哪里”
3. [Reader 扩展](reader_extensions.md) / [Step 扩展](step_extensions.md)
4. [SDK 快速开始](sdk_quickstart.md)
5. [测试与证据矩阵](sop_matrix.md)
6. 按 [测试范式](testing.md) 补增量测试，并运行 `python scripts/test_incremental.py`
7. 新增页面后运行 `python scripts/build_reference_docs.py`

## 3. 文档权威性

| 文档 | 状态 | 用途 |
|---|---|---|
| [vision.md](vision.md) | 当前定位 | 核心价值、支撑手段、差异化与设计判断 |
| [architecture.md](architecture.md) | 当前权威 | 仓库结构、执行流、模块边界、改哪里 |
| [protocol_suite.md](protocol_suite.md) | 当前规范 | 数据/Reader/算子/契约的硬性约定 |
| [reference/](reference/README.md) | 自动生成 | 每个 Reader/算子的参数、契约、源码/测试链接 |
| [reference/subjects/](reference/subjects/README.md) | 人工维护 | 九个系统对象：职责、数据不变量、扩展边界 |
| [route_sop.md](route_sop.md) | 当前流程 | 自定义任务的标准操作流程 |
| [llm_guide.md](llm_guide.md) / [user_guide.md](user_guide.md) | 当前指南 | LLM/真人的操作手册 |
| [testing.md](testing.md) | 当前流程 | 严格增量测试、静态 gate、周期全量 |
| [sop_matrix.md](sop_matrix.md) | 证据快照 | 覆盖级别、oracle、缺口 |
| [r_oracles.md](r_oracles.md) | 专题 | R 包安装与外部 oracle 测试 |
| [windows_compatibility.md](windows_compatibility.md) | 专题 | 原生 Windows 不可用的 Reader/依赖与 WSL 建议 |
| [installation.md](installation.md)、[desktop.md](desktop.md)、[portability.md](portability.md) | 专题 | 安装、桌面、迁移 |
| [input_formats.md](input_formats.md) | 专题 | 输入格式/边界 |
| [resource_runtime.md](resource_runtime.md) | 专题 | 预算、准入、spill |
| [plugins.md](plugins.md)、[dependency_isolation.md](dependency_isolation.md) | 专题 | 插件、依赖隔离 |
| [agent_api.md](agent_api.md) | 专题 | CLI/MCP/Agent |
| [route_operators.md](route_operators.md) | 专题 | 路线复用/注册 |
| [frontend_requirements.md](frontend_requirements.md) | 专题 | Studio 交互 |
| [operator_protocol.md](operator_protocol.md)、[package_protocol.md](package_protocol.md) | 实现细节 | 与协议总集冲突时以协议总集为准 |
| [reader_extensions.md](reader_extensions.md)、[step_extensions.md](step_extensions.md)、[sdk_quickstart.md](sdk_quickstart.md)、[sdk_reference.md](sdk_reference.md) | 实现细节 | 扩展模板/API |
| [microbiome.md](microbiome.md) | 专题 | 16S 示例 |
| [changelog.md](changelog.md) | 历史 | 当前版本摘要；历史从 git tag 查 |

**冲突处理**：架构/协议 > 实现细节 > 历史记录。自动生成的参考页以源码声明为准。旧 release/audit 文档已从工作树移除，需要时从 git 历史查。

## 4. 当前版本与能力

- 版本：**0.88.0**（见 [changelog](changelog.md)）
- 387 个算子、85 个 Reader、6 个 provider 包、21 条内置路线
- 分类统一为 6 类；算子/Reader 功能预览、平台标记与 catalog integrity 检查已接入
- 许可证：Apache License 2.0（见根目录 `LICENSE`/`NOTICE`）
- 所有内置 Reader/算子参数严格（`additionalProperties: false`）
- Reader 覆盖：CSV/TSV/TXT/Parquet、BED/GFF3/GTF/GAF、FASTA、MTX、H5AD、10x H5、VCF、PLINK1/2、BGEN、GMT、Loom、BIOM、FAM/BIM/HapMap、MOL/XYZ/GRO、PSL/genePred、MGF、HMMER domtblout、mzML/mzXML/mzTab、mzIdentML/pepXML/mzDATA/protXML 摘要、FCS/AB1
- 原生 Windows 缺 `pysam`/`pyBigWig`：BAM/CRAM/BCF/BigWig 需 WSL/Linux；见 [Windows 兼容性](windows_compatibility.md)
- 已知边界：mzML/mzXML/mzTab 只输出扫描/记录摘要，不展开原始峰列表；空间转录组/影像等尚未支持
- Windows 环境快照：[conda](../windows-biopipe-conda.yml) / [pip](../windows-biopipe-pip-freeze.txt)

## 5. 最常用的五个命令

```bash
python scripts/test_incremental.py            # 日常严格增量
python scripts/test_incremental.py --full     # 周期全量
python -m biopipe inspect "<绝对路径>" --json
python scripts/run.py tasks/<任务> --check
python scripts/build_reference_docs.py --check
```

## 6. 目录速查

```text
src/core/          Form、契约、错误、数值
src/reader/        Reader 路由与格式
src/task/          manifest、Context、Runner、Step、内存
src/web/           FastAPI、Graph、路线、任务、资产
frontend/          React Studio
biopipe/           CLI、注册表、包、插件、inspect
biopipe_sdk/       公开扩展 SDK
desktop/           WinForms/WebView2 宿主
scripts/           run/studio/registry/文档生成
tasks/             示例任务与自定义任务
routes/            路线模板
tests/             单元、契约、SOP、路线
docs/reference/    自动生成的 Reader/算子参考
```

细节见 [architecture.md](architecture.md)。
