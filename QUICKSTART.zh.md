# BioPipe 快速开始

从一台干净的 Windows 电脑出发，大约五分钟完成：安装桌面应用、导入当前算子库、在
RCSB 结构 **1MEL** 上跑通一个真实的界面分析流程，并导出结果。

BioPipe 完全在本地运行，不上传数据，也不需要单独安装 Python。

## 1. 安装桌面应用

1. 从 [v2.6.0 发行版](https://github.com/lovegavin/BioPipe/releases/tag/v2.6.0)
   下载 **`BioPipe_Setup.exe`**（约 793 MB）。
2. 双击运行。Windows SmartScreen 可能提示“未知发布者”，选择
   **更多信息 → 仍要运行**；安装包目前尚未做代码签名。
3. 安装按当前用户进行：程序位于
   `%LOCALAPPDATA%\Programs\BioPipe Studio`，并创建桌面快捷方式，不需要管理员权限。
4. 每次安装都会生成全新配置目录
   `%USERPROFILE%\.biopipe\profiles\<installation-id>`；重装不会覆盖旧配置和分析文件。

支持平台：64 位 Windows 10 / 11。

## 2. 导入算子库

应用自带一份种子算子库，保证首次启动即可使用。本发行版对应的完整库是
**4.0.2**：717 个算子、101 个 Reader。

1. 从 [library-v4.0.2 发行版](https://github.com/lovegavin/BioPipe/releases/tag/library-v4.0.2)
   下载 **`BioPipe-Library-v4.0.2-Windows.biopipe-library.zip`**；Linux 用户下载
   `Linux` 版本。
2. 在 Studio 中打开 **算子库（Operator Library）→ 导入包（Import package）**。
3. 选择该 zip，等待导入完成。算子库面板会显示版本 **4.0.2**，它与软件版本相互独立。
4. 导入是事务性的：失败时保留原有算子库，不会出现半装状态。

已安装 BioPipe 的 Python 环境也可以用命令行：

```bash
biopipe plugin install BioPipe-Library-v4.0.2-Windows.biopipe-library.zip
```

## 3. 运行示例流程

发行版中的快速开始包 `BioPipe-Quickstart-v4.0.2.zip` 包含下面两个输入文件和一个可直接
导入的流程图。

**输入数据**（均为公开数据）：

| 文件 | 内容 |
| --- | --- |
| `data/vhh_1mel.pdb` | RCSB 条目 [1MEL](https://doi.org/10.2210/pdb1MEL/pdb)：羊驼源 VHH 结构域（链 A、B）与鸡蛋清溶菌酶（链 L、M）的复合物，3,908 个原子 |
| `data/vhh.fasta` | 链 A 的 VHH 序列，132 个残基 |

**流程图**（`vhh_interface.route.json`）：

```
vhh_1mel.pdb ──▶ structure_interface_core ──▶ export_results（interface_residues.csv）
vhh.fasta   ──▶ sequence_liability_scan ──▶ export_results（liabilities.csv）
```

`structure_interface_core` 计算 VHH/溶菌酶界面每个残基埋藏的可及表面积，并把残基分为
核心（core）与边缘（rim）；`sequence_liability_scan` 标注 VHH 序列中的氧化、异构化
和脱酰胺基序。整个流程在普通笔记本 CPU 上只需几秒。

### 方式 A —— 画布

1. 解压快速开始包。
2. 在 Studio 中选择 **文件 → 导入路线包或 JSON（File → Import workflow bundle or JSON）**，
   选中 `vhh_interface.route.json`。
3. 依次选中两个 **Source** 节点，把路径改指到 `data/` 中对应的文件（流程图保存的是相对
   快速开始包的路径，导入后需要重新选择一次）。
4. 点击 **运行（Run）**。

### 方式 B —— 命令行（源码仓库）

在包含 `library/` 与 `examples/` 的仓库根目录执行：

```bash
python -m biopipe --workspace "$PWD" run examples/quickstart/vhh_interface.route.json --wait
```

导出的文件位于 `output/artifacts/exports/<hash>/`。

## 4. 导入现成路线（可选）

发行资产还包含 `BioPipe-Routes-v<version>.zip`。解压后，其中每个
`routes/<key>.biopipe.zip` 就是一条完整的内置路线。

- Studio：**文件 -> 导入路线包或 JSON**，选择一个包，再把 Source 节点指向你的文件。
- 命令行：`biopipe graph open routes/<key>.biopipe.zip`（源文件就绪后也可 `biopipe run`）。

该包覆盖本算子库内置的路线，包括变异 QC/一致性、单细胞与 RNA-seq 分析。

## 5. 预期结果

| 指标 | 数值 |
| --- | --- |
| 界面残基总数 | **88** |
| 核心残基（core） | **52** |
| 边缘残基（rim） | **36** |
| 序列风险位点 | **10**（5 个氧化、3 个异构化、2 个脱酰胺） |

导出的两张表：

- `interface_residues.csv` —— 88 行，列为
  `residue,delta_sasa,isolated_sasa,buried_fraction,is_core`。
- `liabilities.csv` —— 10 行，列为
  `liability,position,severity_code,motif_length`。

界面表第一行是 `A:ILE:29`（埋藏比例 0.537）；风险表第一行是 `33:oxidation`
（基序 `M`，上下文 `PYCMGWF`）。

## 6. 让 agent 来驱动

如果已经通过 MCP 接入 agent（Studio 的 **Agent 面板**会生成配置；详见
`docs/quickstart_full_flow.zh.md` 第 5 节），把下面的提示词粘贴进去：

```text
在做任何事之前，先阅读 QUICKSTART.zh.md 和 docs/agent_bootstrap.md。
然后调用 biopipe_status，列出当前会话，并用 biopipe_context 查看画布现状；
此时不要修改任何内容。

使用本快速开始包中的 vhh_1mel.pdb 与 vhh.fasta（源码仓库中位于
examples/quickstart/data），提出一个四算子流程图：
  PdbReader -> structure_interface_core -> export_results（CSV）
  FastaReader -> sequence_liability_scan -> export_results（CSV）
告诉我算子参数和预期输出，然后等待我确认。确认后再运行，汇报
n_interface/n_core/n_rim、风险位点数量，并列出导出的文件。
```

agent 必须先读文档、先查看画布再编辑、用一次带 revision 校验的事务完成修改，并且在
真正运行前等待用户明确确认——这些规则写在 `docs/agent_bootstrap.md` 中。

## 7. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| SmartScreen 阻止安装 | 选择 **更多信息 → 仍要运行**；安装包未签名。 |
| 报 `Missing operator definition: export_results` | 当前 workspace 没有算子库。启动 Studio 并导入库 zip，或把 `--workspace` 指向包含 `library/` 的仓库根目录。 |
| 任务一直 `queued`，提示 “Waiting for available host memory” | 长时间运行的 Studio 可能持有过期的内存快照。完全退出 Studio 后重新打开，启动时会重新扫描主机内存。 |
| 导入 zip 被拒绝 | 请使用 `.biopipe-library.zip` 资产，而不是 seed `.whl`；库包会校验自身 checksum 与包版本。 |

日志位置：安装日志在 `%LOCALAPPDATA%\BioPipe\Setup\<timestamp>`，运行日志在配置目录对应的
作业目录下。
