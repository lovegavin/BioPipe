# BioPipe 快速开始（应用 2.6.0 + 算子库 4.0.4）

> 此文保留原先固定版本的算子库演示。当前 **Operon 3.0.1** 请先按
> [Windows 安装指南](docs/windows_setup.md) 或 [Windows/Linux 命令行安装指南](docs/command_line_installation.md)
> 安装，再按[运行环境准备指南](docs/readiness.md)显式检查并准备所选路线的依赖。
> 下文的安装路径、安装包名称和随包依赖描述仍对应 2.6.0。

从一台干净的 Windows 电脑出发，大约五分钟完成：安装桌面应用、导入 4.0.4 算子库、
在 **1MEL** 上跑通一个真实的 VHH/溶菌酶界面分析，并导出结果。

BioPipe 完全在本地运行，不上传数据，也不需要单独安装 Python。

## 0. 版本

| 组件 | 版本 |
| --- | --- |
| 桌面应用 / 前端 | **2.6.0** |
| 算子库（后端） | **4.0.4**（717 个算子、101 个 Reader、7 个包、24 条路线） |
| 协议 | v3 |
| 最低应用版本 | 2.6.0 |

应用和算子库独立升级：应用升级不覆盖已导入的库。快速开始只提供本文件和
`QUICKSTART.md` 两份文档；示例数据就在源码仓库里，不再单独打包。

## 1. 安装桌面应用

1. 从 [v2.6.0 发行版](https://github.com/lovegavin/BioPipe/releases/tag/v2.6.0)
   下载 **`BioPipe_Setup.exe`**（约 793 MB）。
2. 双击运行。SmartScreen 提示“未知发布者”时选择 **更多信息 → 仍要运行**；
   安装包目前尚未代码签名。
3. 安装按当前用户进行：程序位于
   `%LOCALAPPDATA%\Programs\BioPipe Studio`，并创建桌面快捷方式，不需要管理员权限。
4. 每次安装生成独立配置目录
   `%USERPROFILE%\.biopipe\profiles\<installation-id>`；重装不会覆盖旧配置。

支持 64 位 Windows 10 / 11。

## 2. 导入算子库 4.0.4

1. 从 [library-v4.0.4 发行版](https://github.com/lovegavin/BioPipe/releases/tag/library-v4.0.4)
   下载对应平台的库包：
   - Windows：`BioPipe-Library-v4.0.4-Windows.biopipe-library.zip`
   - Linux：`BioPipe-Library-v4.0.4-Linux.biopipe-library.zip`
2. Studio → **算子库 → 导入包**，选中 zip，等待完成。
3. 面板显示 **4.0.4** 即成功。导入是事务性的：失败会保留原库，不会半装。
4. 平台必须匹配；装错会报 `Library source does not match wheel`。

已安装的 Python 环境也可以：

```bash
biopipe --profile-dir <profile> plugin install \
  BioPipe-Library-v4.0.4-Windows.biopipe-library.zip
```

验证注册表：

```bash
biopipe --profile-dir <profile> registry check
# operators 717 / readers 101 / packages 7 / routes 24 / errors 0
```

`registry check` 只校验协议与注册表，不校验分析依赖；依赖面板里的缺失项按需安装，
不影响本快速开始。

## 3. 连接方式一：agent + MCP（推荐）

### 3.1 启动 MCP 服务

打开 Studio 的 **Agent 面板**，它会生成当前 profile 的 MCP 配置。把类似下面的 JSON
粘贴到 agent 客户端（Claude Desktop、Cursor、DeepSeek Harness 等）的 MCP 配置中：

```json
{
  "mcpServers": {
    "biopipe": {
      "command": "<安装目录>\\biopipe.exe",
      "args": ["mcp", "--allow-run"]
    }
  }
}
```

- `command` 用面板生成的绝对路径；Linux 上通常是已安装环境里的 `biopipe`。
- `--allow-run` 允许 agent 提交任务；只读场景改成 `--read-only`。
- 需要安装插件时再加 `--allow-plugins`。
- 改完配置后**重启 agent 客户端**，新会话里应出现 `biopipe_*` 工具。

### 3.2 验证连接

在 agent 里依次调用：

```text
biopipe_status()             # 连接、版本、workspace
biopipe_sessions()           # 当前画布会话
biopipe_context(session_id)  # 选中节点、参数、revision
```

能返回当前 workspace、717 个算子与 101 个 Reader，即连接成功。

### 3.3 让 agent 跑 1MEL

确认已连通后，把下面这段**原样**发给 agent：

```text
使用本快速开始包中的 vhh_1mel.pdb 与 vhh.fasta（源码仓库中位于examples/smoke_real_data/input），提出一个有深度研究价值的科学问题，先输出得到确认，再设计分析图，在远程服务器或本地运行，自行检查算子的输出与结果，得到严谨的科学结论
```

说明（不要混进上面的命令）：

- 数据在源码仓库的 `examples/smoke_real_data/input/`；没有源码 checkout 时，可在
  Studio 里用任意本地路径的同名文件。
- agent 会先给科学问题与图，**等你确认后**才运行；运行位置由当前执行目标决定
  （本地，或第 4 节的服务器）。
- agent 的硬规则在 `docs/agent_bootstrap.md`：先读画布、用 `expected_revision` 做事务、
  运行前等确认、结果必须来自 `biopipe_artifacts` / `biopipe_artifact_table`。

## 4. 连接方式二：远程 Linux 服务器

数据在服务器、或本机算力不够时使用。桌面端负责编辑与展示，计算在服务器执行。

### 4.1 首次安装服务器

1. Studio 顶部工具栏选择 **执行目标 → 服务器维护 → 安装 / 升级服务器**。
2. 填 SSH 地址、端口、用户名，选择密钥或密码；首次连接确认主机指纹。
3. 安装器自动下载 micromamba，在服务器创建 Python 3.11 环境（含 BWA、samtools、
   pairtools、cooler、cooltools），不需要 sudo，也不改系统 Python。
4. 默认安装目录 `$HOME/.local/share/biopipe`，运行目录是其下的 `workspace/`；
   可在连接面板修改。
5. 安装成功会写入稳定的 `server.json`；以后连接直接复用，不重复安装。

安装日志在服务器 `managed-v1/setup-<digest>.log`。安装失败不会发布新的安装指针，
可重试。已有环境可手动注册：

```bash
python -m biopipe.remote.installation register \
  --app-dir /srv/biopipe --workspace /srv/biopipe-work
```

然后在桌面端选择 **手动指定环境**。

### 4.2 在服务器上运行

1. 工具栏把执行目标切到该服务器。
2. Source 节点可以直接浏览服务器上的文件；Check / Run 通过 SSH 执行。
3. 结果与日志仍在 Studio 中查看，不需要手动 scp。

### 4.3 agent 走服务器

agent 仍连本地 Studio，只需切换执行设备：

```text
biopipe_remote_status()                 # profile 是否已连接
biopipe_remote_ensure(profile_id)       # 断线时重连
biopipe_set_execution(session_id, document_id, expected_revision,
                      {"kind": "ssh", "profile_id": "<id>"})
```

之后 `biopipe_validate` / `biopipe_run` / `biopipe_submit` 在服务器执行；
`biopipe_artifacts`、`biopipe_artifact_table`、`biopipe_logs` 直接读远端结果。

## 5. 不用 agent：画布与 CLI

数据与路线都在源码仓库：

| 文件 | 位置 |
| --- | --- |
| 结构 | `examples/smoke_real_data/input/vhh_1mel.pdb` |
| 序列 | `examples/smoke_real_data/input/vhh.fasta` |
| 路线 | `examples/quickstart/vhh_interface.route.json` |

1MEL 是羊驼源 VHH（链 A、B）与鸡蛋清溶菌酶（链 L、M）的复合物，3,908 个原子；
FASTA 是链 A 的 132 个残基。

### 方式 A —— 画布

1. Studio → **文件 → 导入路线包或 JSON**，选择 `vhh_interface.route.json`。
2. 选中两个 **Source** 节点，把路径改到 `examples/smoke_real_data/input/` 下的
   `vhh_1mel.pdb` 与 `vhh.fasta`（路线保存的是相对旧位置的路径，导入后需重选一次）。
3. 点击 **运行**，普通笔记本 CPU 约 4 秒。

### 方式 B —— 命令行

在仓库根目录，先把路线里两个 Source 的 `path` 改到 `examples/smoke_real_data/input/`，
然后：

```bash
python -m biopipe --workspace "$PWD" \
  run examples/quickstart/vhh_interface.route.json --wait
```

导出位于 `output/artifacts/exports/<hash>/`。

## 6. 预期结果与自查

| 指标 | 数值 | 容差 |
| --- | --- | --- |
| 界面残基总数 | **88** | 精确 |
| 核心残基（core） | **52** | 精确 |
| 边缘残基（rim） | **36** | 精确 |
| 序列风险位点 | **10**（5 氧化、3 异构化、2 脱酰胺） | 精确 |
| 全结构 SASA（518 残基） | **21,803.1 Å²** | ±0.5% |

- `interface_residues.csv`：88 行，列
  `residue,delta_sasa,isolated_sasa,buried_fraction,is_core`；
  第一行 `A:ILE:29`，`buried_fraction = 0.537`，`is_core = 1`。
- `liabilities.csv`：10 行，列
  `liability,position,severity_code,motif_length`；
  第一行 `33:oxidation`，基序 `M`，上下文 `PYCMGWF`。

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
| agent 看不到 `biopipe_*` 工具 | MCP 配置未生效；检查 command 路径与 `--allow-run`，重启客户端。 |
| `Missing operator definition: export_results` | 当前 workspace 没加载库；先在 Studio 导入 4.0.4，或用 `--profile-dir` 指向已导入库的 profile。 |
| `Library source does not match wheel` | 平台包用错；Windows/Linux 选对应 zip，原库不变。 |
| 服务器安装失败 | 看 `managed-v1/setup-<digest>.log`；确认 SSH、磁盘、出站 HTTPS。 |
| 服务器连上但算子不可用 | 服务器 profile 未导入 4.0.4，或依赖未装；先导入库，再按依赖面板安装。 |
| 任务长时间 `queued` | 长时间运行的 Studio 可能持有过期内存快照；完全退出后重开。 |

日志：安装日志在 `%LOCALAPPDATA%\BioPipe\Setup\<timestamp>`；运行日志在配置目录的
`logs/` 下；服务器日志在 `managed-v1/setup-<digest>.log`。

## 8. 下一步

- 24 条内置路线：**文件 → 打开路线**。
- 参数、端口与错误：选中节点看 **Inspector** 与运行日志。
- 协议与扩展：`docs/operator_protocol.md`、`docs/step_extensions.md`。
- agent 规则与工具：`docs/agent_bootstrap.md`、`docs/agent_api.md`。
