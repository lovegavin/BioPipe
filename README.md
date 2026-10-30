# BioPipe

BioPipe 是本地生信流水线引擎 + Studio 可视化工作区 + CLI/MCP Agent 接口。它用
Reader 读取标准格式，用带类型契约的算子处理 `Form`，并在本地生成表格、图片和报告。
BioPipe 本身不提供 AI 服务。

当前源码版本 **0.35.0**：**251 个算子、82 个 Reader、6 个 provider 包、21 条路线**。

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

最值得先读的四份：

| 文档 | 作用 |
|---|---|
| [架构总览](docs/architecture.md) | 仓库结构、执行流、模块边界、改哪里 |
| [协议总集](docs/protocol_suite.md) | Form/Reader/算子/契约/注册表/扩展/测试规范 |
| [参考索引](docs/reference/README.md) | 每个 Reader/算子的参数、契约、源码/测试链接 |
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
- 原生 Windows 缺 `pysam`/`pyBigWig`：BAM/CRAM/BCF/BigWig 请用 WSL/Linux；见
  [Windows 兼容性](docs/windows_compatibility.md)。
- 尚未覆盖：原始峰列表、空间转录组、影像。
- 大矩阵/内存：heatmap 有 `max_cells`/`max_pixels` 保护；H5AD/10x full 模式仍可能 densify。
- 21 条 route 均有仓库内 fixture，pytest 会实际执行；真实数据 demo 另行覆盖。

## 版本与更新记录

- 当前：**0.35.0**，见 [CHANGELOG](docs/changelog.md)。
- Windows 测试环境快照：[conda](windows-biopipe-conda.yml) /
  [pip](windows-biopipe-pip-freeze.txt)。

## 许可证

Copyright (c) 2026 Haojian Li. All rights reserved.

This software is proprietary. No part of this software may be copied, modified,
distributed, sublicensed, or used for commercial purposes without the prior
written permission of the copyright holder.

商业授权/合作：lovegavin118@outlook.com / WeChat: mylovegavin118 / 13727316173。
