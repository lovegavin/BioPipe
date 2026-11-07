# Operon 快速开始（Studio 3.0.2 + 算子库 5.0.1）

从一台干净的 Windows 电脑出发，大约五分钟完成：安装 Operon Studio 3.0.2、导入 5.0.1
算子库，在 **1MEL** 上跑通一个真实的 VHH/溶菌酶界面分析，并导出结果。

Operon 完全在本地运行，不上传数据，也不需要单独安装 Python。

## 0. 版本

| 组件 | 版本 |
| --- | --- |
| 桌面应用 / 前端 | **3.0.2** |
| 算子库（后端） | **5.0.1**（867 个算子、108 个 Reader、7 个包、72 条路线） |
| 协议 | v3 |
| 最低应用版本 | 3.0.2 |

应用和算子库独立升级：应用升级不覆盖已导入的库。下文的示例位于源码仓库的
`examples/quickstart/`；`QUICKSTART.md` 与 `QUICKSTART.zh.md` 既随库单独发布，也包含在
`Operon-Quickstart-v5.0.1.zip` 中。

## 1. 安装 Operon Studio 3.0.2

1. 从 [v3.0.2 发行版](https://github.com/lovegavin/Operon/releases/tag/v3.0.2)
   下载 **`Operon_Setup.exe`**。
2. 双击运行。SmartScreen 提示“未知发布者”时选择 **更多信息 → 仍要运行**；
   安装包目前尚未代码签名。
3. 安装按当前用户进行：程序位于 `%LOCALAPPDATA%\Programs\Operon Studio`，
   并创建桌面和开始菜单快捷方式，不需要管理员权限。
4. 每次安装生成独立配置目录 `%USERPROFILE%\.operon\profiles\<installation-id>`；
   重装会保留旧配置，并从一个空 workspace 开始。

3.0.2 安装包内置的是**管理运行时**（HTTP/MCP/SSH 以及用于内存与预览的 NumPy），
不是完整的科学计算环境。算子清单、代码和文档无需分析包即可加载；Pandas、SciPy、
h5py 等依赖在运行具体路线时显式准备，首次准备需要联网。

支持 64 位 Windows 10 / 11。

## 2. 导入算子库 5.0.1

1. 从 [library-v5.0.1 发行版](https://github.com/lovegavin/Operon/releases/tag/library-v5.0.1)
   下载对应平台的库包：
   - Windows：`Operon-Library-v5.0.1-Windows.operon-library.zip`
   - Linux：`Operon-Library-v5.0.1-Linux.operon-library.zip`
2. Studio → **算子库 → 导入包**，选中 zip，等待完成。
3. 面板显示 **5.0.1** 即成功。导入是事务性的：失败会保留原库，不会半装。
4. 平台必须匹配；装错会报 `Library source does not match wheel`。

> **旧后缀说明。** 文件选择器和上传接口仍接受旧的 `.biopipe-library.zip`，
> 但安装路由是严格的：只有 `.operon-library.zip`（`format: "operon.library"`）
> 能完整安装。旧归档能通过选择器，却会在安装阶段失败，请使用上面的 5.0.1 库包。
> 该差异记录在
> [docs/verification/operon-5.0.0-compatibility.md](docs/verification/operon-5.0.0-compatibility.md)。

已安装的 Python 环境也可以：

```bash
operon --profile-dir <profile> plugin install \
  Operon-Library-v5.0.1-Windows.operon-library.zip
```

验证注册表：

```bash
operon --profile-dir <profile> registry check
# operators 867 / readers 108 / packages 7 / routes 72 / errors 0
```

`registry check` 只校验协议与注册表，不校验分析依赖；缺失项显示在依赖面板中，
只有在你准备运行环境时才会安装。

## 3. 导入并运行示例路线

数据与路线都在源码仓库：

| 文件 | 位置 | 大小 |
| --- | --- | --- |
| 结构 | `examples/quickstart/data/vhh_1mel.pdb` | 361,017 B |
| 序列 | `examples/quickstart/data/vhh.fasta` | 145 B |
| 路线 | `examples/quickstart/vhh_interface.route.json` | — |

1MEL 是羊驼源 VHH（链 A、B）与鸡蛋清溶菌酶（链 L、M）的复合物，3,908 个原子；
FASTA 是链 A 的 132 个残基。两个文件都是公开的 1MEL 派生输入
（sha256 `321aa847…24de4` 与 `7d148d84…4fa5`）。

路线是自包含的：`base_dir` 为 `examples/quickstart`，因此当仓库根目录就是 workspace 时，
两个 Source 节点可直接解析 `data/vhh_1mel.pdb` 与 `data/vhh.fasta`。若把路线复制到别处，
选中两个 Source 节点重新指向一次即可。

计算图：两个 Source → `structure_interface_core`（binder 链 `A,B`、target 链 `L,M`、
`core_fraction` 0.5、`probe_radius` 1.4、92 个表面点）与 `sequence_liability_scan`
（氧化及脱酰胺/异构化基序，±3 上下文）→ 两个 `export_results` CSV 节点。

### 画布

1. Studio → **文件 → 导入路线包或 JSON**，选择 `vhh_interface.route.json`。
2. 点击 **校验（Validate）**。若环境被阻塞，先为该路线准备一次依赖
   （biopython、h5py、hictkpy、numpy、scipy）；校验与运行本身从不安装任何东西。
3. 点击 **运行**，普通笔记本 CPU 约 4 秒。

### 命令行

在仓库根目录：

```bash
python -m operon --workspace "$PWD" \
  run examples/quickstart/vhh_interface.route.json --wait
```

导出位于 `output/artifacts/exports/<hash>/`。

## 4. 可选：agent + MCP

打开 Studio 的 **Agent 面板**，它会生成当前 profile 的 MCP 配置。把类似下面的 JSON
粘贴到 agent 客户端的 MCP 配置中：

```json
{
  "mcpServers": {
    "operon": {
      "command": "<安装目录>\\operon.exe",
      "args": ["mcp", "--allow-run"]
    }
  }
}
```

- `--allow-run` 允许 agent 提交任务；只读场景改成 `--read-only`。
- 需要安装插件时再加 `--allow-plugins`。
- 改完配置后**重启 agent 客户端**，新会话里应出现 `operon_*` 工具。

用 `operon_status()`、`operon_sessions()` 与 `operon_context(session_id)` 验证连接：
能返回当前 workspace 和 5.0.1 注册表即连接成功。

## 5. 可选：远程 Linux 服务器

桌面端负责编辑与展示，计算在服务器执行。选择 **执行目标 → 服务器维护 → 安装 / 升级服务器**，
填写 SSH 地址、端口和用户名，并确认主机指纹。安装器会在 `$HOME/.local/share/operon`
下创建独立的 Python 3.11 环境（micromamba、BWA、samtools、pairtools、cooler、cooltools），
不需要 sudo，并写入可复用的 `server.json`。之后切换执行目标，用校验 / 运行执行；
结果与日志仍在 Studio 中查看。走 agent 时先用 `operon_remote_status()`、
`operon_remote_ensure(profile_id)` 与 `operon_set_execution(...)`，让 `operon_run` /
`operon_submit` 在远端执行。

## 6. 预期结果与自查

已在 1MEL 上用 5.0.1 算子库验证：

| 指标 | 数值 |
| --- | --- |
| 界面残基总数 | **88** |
| 核心残基（`is_core = 1`） | **52** |
| 边缘残基（rim） | **36** |
| 序列风险位点 | **10**（5 氧化、3 异构化、2 脱酰胺） |

- `interface_residues.csv`：88 行，列
  `residue,delta_sasa,isolated_sasa,buried_fraction,is_core`；第一行 `A:ILE:29`，
  `buried_fraction ≈ 0.537`，`is_core = 1`。
- `liabilities.csv`：10 行，列
  `liability,position,severity_code,motif_length`；第一行 `33:oxidation`。

```python
import pandas as pd
i = pd.read_csv("interface_residues.csv")
l = pd.read_csv("liabilities.csv")
assert len(i) == 88 and int(i.is_core.sum()) == 52
assert abs(i.iloc[0].buried_fraction - 0.537) < 0.002
assert len(l) == 10 and l.iloc[0].liability == "33:oxidation"
print("OK", i.residue.iloc[0], l.liability.iloc[0])
```

## 7. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| agent 看不到 `operon_*` 工具 | MCP 配置未生效；检查 command 路径与 `--allow-run`，重启客户端。 |
| `Missing operator definition: export_results` | 当前 workspace 没加载库；先在 Studio 导入 5.0.1，或用 `--profile-dir` 指向已导入库的 profile。 |
| `Library source does not match wheel` | 平台包用错；Windows/Linux 选对应的 5.0.1 zip，原库不变。 |
| `The selected execution environment is not ready` | 先为该路线显式准备依赖，再校验一次；校验与运行不会安装任何包。 |
| 服务器安装失败 | 看 `managed-v1/setup-<digest>.log`；确认 SSH、磁盘、出站 HTTPS。 |
| 任务长时间 `queued` | 长时间运行的 Studio 可能持有过期内存快照；完全退出后重开。 |

日志：安装日志在 `%LOCALAPPDATA%\Operon\Setup\<timestamp>`；运行日志在配置目录的
`logs/` 下；服务器日志在 `managed-v1/setup-<digest>.log`。

## 8. 下一步

- 5.0.1 库内置 72 条路线：**文件 → 打开路线**。
- 参数、端口与错误：选中节点看 **Inspector** 与运行日志。
- 协议与扩展：`docs/operator_protocol.md`、`docs/step_extensions.md`。
- agent 规则与工具：`docs/agent_bootstrap.md`、`docs/agent_api.md`。
