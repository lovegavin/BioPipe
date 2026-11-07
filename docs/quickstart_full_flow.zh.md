# Operon 快速开始（中文）

英文版见 [quickstart_full_flow.en.md](quickstart_full_flow.en.md)。

## 0. 预检

```text
python --version      # 3.11 或 3.12
node --version        # 22.12 及以上
git --version
```

## 1. 安装本地后端

```text
python -m venv .venv
.venv\Scripts\activate            # Windows
python -m pip install -e ".[agent,dev]"
python -c "import operon; print(operon.__version__)"
python -m operon registry check   # 期望 errors []
```

`.[agent]` 提供 MCP；`.[dev]` 提供测试工具。可选分析依赖在
`requirements-readers.txt` 和 `requirements-analysis.txt`。

## 2. 构建本地前端

```text
cd frontend
npm install
npm run build
cd ..
```

开发模式（改前端时用）：`npm run dev`，同时后端用
`python scripts/studio.py --dev`。

## 3. 启动 Studio

```text
python scripts/studio.py --profile-dir operon-v3-test
```

打开 <http://127.0.0.1:8765>。首次启动会生成演示工作流。默认 profile 是
`~/.operon/studio`；`--profile-dir` 用于隔离，避免影响已发布的桌面配置。

## 4. 连接远程服务器（可选，约 5 分钟准备）

本机跑得动就跳过本节。远程服务器只需一次性准备：能 SSH 登录、有 Python 3.11+（托管模式不需要预装）。

进入 **执行环境 / 服务器** 页面，按下表填写；连接成功后才会确认指纹、上传源码并安装环境。

| 字段 | 含义 | 必填 / 默认 | 示例 |
| --- | --- | --- | --- |
| 名称 | 本机列表显示名 | 必填 | `计算服务器` |
| 主机 | IP 或域名 | 必填 | `172.22.148.93` |
| 端口 | SSH 端口 | 默认 `22` | `22` |
| 用户名 | Linux 账号 | 必填 | `lihj` |
| 服务器环境 | 托管=Operon 装独立环境；手动=复用已有环境 | 默认托管 | `已安装的 Operon 服务端` |
| 安装目录 | 托管模式根目录；换目录即全新环境 | 可选，绝对路径 | `/public/home/lihj/operon-accept` |
| Operon 目录 | 手动模式代码根（含 `src/`、`pyproject.toml`） | 手动必填 | `/opt/operon` |
| Python | 手动模式解释器 | 手动必填，默认 `python3` | `/opt/conda/envs/operon/bin/python` |
| 运行目录 | 远端任务与产物根 | 手动必填；托管留空自动创建 | `/public/home/lihj/operon-work` |
| 认证方式 | 密码 / 私钥文件 / SSH Agent | 默认密码 | `私钥文件` |
| 密码 | 仅本次会话，不落盘 | 密码认证时填 | — |
| 本机私钥路径 | 运行前端的本机私钥，不是服务器路径 | 私钥认证时填 | `~/.ssh/id_rsa` |
| 私钥口令 | 私钥口令 | 可选 | — |
| SSH 网关 | 普通 SSH / 交互式网关 | 默认普通 | `普通 SSH` |
| 实例编号 | 交互式网关的菜单编号 | 网关模式填 | `0` |

- 路径必须为绝对 Linux 路径且不含 `..`；端口 `1–65535`。
- 首次连接会显示主机指纹，确认后才上传源码、安装 micromamba 与依赖；完成标志 `env-*/operon-ready.json`，日志 `setup-*.log`。
- 验收用全新 `安装目录`，不要复用已测环境。

## 5. 连接 MCP（首选 DeepSeek Harness）

DSH 的 MCP 客户端配置在 `%USERPROFILE%\.dsh\profiles\desktop\cordis.patch.yml`：

```yaml
- id: mcp-operon
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: "operon"
    transport: "stdio"
    command: "<python-executable>"
    args:
      - "-m"
      - "operon"
      - "--workspace"
      - "<Operon-workspace>"
      - "--data-dir"
      - "<Operon-data-directory>"
      - "mcp"
      - "--allow-run"
```

| 项 | 建议 | 说明 |
| --- | --- | --- |
| 工作区 | Operon 仓库根（如 `<Operon-workspace>`）或专用数据目录 | 下文的示例路线用相对路径，必须选仓库根；不要把 系统目录、盘符根、整个用户目录设为工作区 |
| 文件权限 | 默认 `workspace-write` | 只写工作区与临时目录；不要为常规分析开 `danger-full-access` |
| MCP 权限 | `mcp --allow-run` | 允许校验与提交运行；只读排查去掉；禁止编辑再加 `--read-only` |
| 插件 | 默认不加 | 仅安装受信插件时加 `--allow-plugins` |

- `--workspace` 与 `--data-dir` 必须与 Studio 的启动参数一致，否则 agent 与画布看到的路由不同。
- 画布工具：`operon_open(document_id=…)` 写入已有标签页（`mode=replace` 覆盖、`append` 新开），
  `operon_apply({op:"set_graph"})` 整图替换，`operon_set_execution(...)` 切换本地/服务器执行设备，
  `operon_status()` 查看连接、权限、版本与会话。
- 改完重启 DSH 与 Studio；在 DSH 里让 agent 调 `operon_operator_search` 验证。
- 其他客户端（Cursor/Claude Desktop）用等价 JSON：`{"mcpServers":{"operon":{"command":"operon","args":["mcp","--allow-run"]}}}`；Studio 的 **Agent 面板** 会按当前解释器生成可直接粘贴的配置。

### 首轮开场白（复制即用）

配置好 MCP、新开一个 agent 对话后，第一条消息只需要：

```text
请阅读 docs/agent_bootstrap.md，准备后续工作。
```

agent 会先调用 `operon_status`、`operon_context` 读环境与画布，然后等你提出需求；
之后正常说话即可，不需要记工具名。

控制台与结果：无论任务由前端、agent 还是终端发起，都会进入 **已执行任务** 列表；
本地与 ssh 任务都能预览、分页查看带标签表格（`operon_artifact_table` 同源）并下载到本地。
任务在准入额度内可并行；前端发起的运行不会因 agent 或终端提交新任务而丢失结果预览。

## 6. 让 Agent 设计并运行第一条路线（真实数据）

示例目录 `examples/smoke_real_data/input/` 只有两个真实文件，**没有现成路线**：

- `vhh_1mel.pdb`：RCSB 1MEL，3908 原子，VHH `A/B` + 溶菌酶 `L/M`；
- `vhh.fasta`：从该结构链 `A` 提取的 132 aa VHH 序列。

这一步验证 Agent 的完整闭环：从算子目录设计路线、**先给方案等你确认**、按指令微调、校验、提交。
在 DSH 中粘贴：

```text
用工作区里的 examples/smoke_real_data/input 做一条路线，不限方向，我需要有极具价值的分析。
先给我节点、参数和预计产物，我确认后再运行。
```

这里的两个真实输入是：

- `vhh_1mel.pdb`：RCSB 1MEL，3908 原子，VHH `A/B` + 溶菌酶 `L/M`；
- `vhh.fasta`：从该结构链 `A` 提取的 132 aa VHH 序列。

Agent 应先用 `operon_operator_search`/`operon_operator_describe` 选算子，给出节点、边、
参数与预计产物，并说明分析价值；你确认后它才 `operon_submit`。不要读取或复用仓库里任何
现成 route.json / task.yaml，路线必须由它从算子目录设计。

数据位置二选一：
- **本地**：`examples/smoke_real_data/input/vhh_1mel.pdb` 与 `vhh.fasta`（工作区为仓库根）
- **服务器**：`/public/home/lihj/operon-work/smoke_real_data/vhh_1mel.pdb` 与 `vhh.fasta`
  （先把执行设备切到服务器 profile；agent 会调用 `operon_remote_ensure` 自检连接）

本地任务提示词：

```text
用工作区里的 examples/smoke_real_data/input 做一条路线：结构做界面 core/rim，序列做 liability；
链 A,B 对 L,M，参数用默认值。先给我节点、参数和预计产物，我确认后再运行。
```

服务器任务提示词：

```text
用服务器 licai-srv-node80 上的 /public/home/lihj/operon-work/smoke_real_data 做一条路线，不限方向，
我需要有极具价值的分析。先给我节点、参数和预计产物，我确认后再运行；执行设备切到该服务器。
```

参考基线（用于判断结果是否合理）：界面残基 **99**（core **58**、rim **41**），
序列 liability **10**（氧化 5、异构化 3、脱酰胺 2），CPU 约 3 秒。数值偏差通常来自
链选择或 cutoff 不同——先看 Agent 的参数摘要，再决定是否让它调整。

回归自检（仅开发者用，不属于练习）：

```bash
python -m operon --workspace <Operon 根目录> workflow validate tests/fixtures/smoke_route/route.json --require-files
```

## 7. 编辑画布

- 左侧算子库搜索后拖入画布，连线决定数据流；右侧面板填参数。
- 输入端口接受注册过的 Reader（FASTA、PDB、CSV、10x MTX、PLINK 等）。
- `Ctrl+Z` 撤销；每次拖拽/连线/参数修改都是一个可撤销事务。
- 选择节点后 **Agent → Copy selection context**，可把当前选择发给 agent。

## 8. 发起运行

三种入口，效果一致（同一个应用服务）：

1. **前端**：选中输出节点或整张图，点 **运行**；第一次运行需要确认执行权限。
2. **Agent**：`operon_submit`（带 `--allow-run`），再 `operon_job` 轮询。
3. **CLI**：

```text
python scripts/run.py <task 目录或工作流 JSON> --check   # 只校验
python scripts/run.py <task 目录或工作流 JSON>           # 真正执行
```

## 9. 查看结果

运行结束在 **Jobs / 运行记录** 里看日志与状态；**Artifacts** 面板按算子输出分组，
可预览表格/图片/结构文件并导出。MCP 用 `operon_artifacts` 取同样的产物列表。

## 10. 常见问题

| 现象 | 处理 |
| --- | --- |
| MCP 工具调用被拒绝 | 检查是否加 `--allow-run`；只读模式不能提交 |
| 前端打开是空白 | 先 `npm run build`；开发模式需同时起 `npm run dev` |
| 远程安装卡住 | 看 `~/.local/share/operon/managed-v1/setup-*.log`，见 `agent_environment_repair.md` |
| 服务器算子提示缺 openmm/antifold | 按 `agent_environment_repair.md` 安装可选依赖 |
| 端口被占用 | `scripts/studio.py --port 8766` |
| 想隔离实验 | `--profile-dir <name>` + `--workspace <dir>` 同时指定 |

## 11. 从零干净验收（最终测试）

需求：最终验收必须是本地前端从零向服务器发起的一次安装；已测试环境可以保留，但测试
环境必须干净。

1. backend 更新到最新 `<Operon-directory>`（版本号见 `operon/__init__.py`）。
2. 选一个全新 base 目录（连接服务器时填写），例如 `~/operon-clean-test`，不要复用
   已有 `managed-v1`。也可以保留 base 但删除测试用环境：
   `rm -rf <base>/env-*`（保留 `mamba-cache`、`~/.cache/pip` 可以加速，不影响"干净"）。
3. 确认干净：`ls <base>/env-*/operon-ready.json` 不存在，且没有旧 `server.json`
   指向已装环境。
4. 在本地前端连接服务器，观察安装进度；首次下载约 8–12 GB。
5. 通过标志：`operon-ready.json` 存在、`pip check` 无输出、日志末尾
   `Operon and Hi-C environment ready`。
6. 记录版本、registry 计数、耗时、env 大小与日志尾部，作为验收证据。

注意：不要预先 `register` 环境；手工部署的环境只作为缓存与证据，不参与本次验收。
