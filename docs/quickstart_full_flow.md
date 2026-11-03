# 完整流程快速开始

从零到"前端发起运行"的最短路径。命令默认在仓库根目录执行，平台示例以 Windows 为主，
Linux/macOS 把激活脚本换成 `source .venv/bin/activate` 即可。

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
python -c "import biopipe; print(biopipe.__version__)"
python -m biopipe registry check   # 期望 errors []
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
python scripts/studio.py --profile-dir biopipe-v3-test
```

打开 <http://127.0.0.1:8765>。首次启动会生成演示工作流。默认 profile 是
`~/.biopipe/studio`；`--profile-dir` 用于隔离，避免影响已发布的桌面配置。

## 4. 连接 MCP（首选 DeepSeek Harness）

DSH 的 MCP 客户端配置在 `%USERPROFILE%\.dsh\profiles\desktop\cordis.patch.yml`，
BioPipe 条目形如：

```yaml
- id: mcp-biopipe
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: "biopipe"
    transport: "stdio"
    command: "C:\\Users\\<you>\\AppData\\Local\\Programs\\Python\\Python312\\python.exe"
    args:
      - "-m"
      - "biopipe"
      - "--workspace"
      - "C:\\Users\\<you>\\.biopipe\\studio\\workspace"
      - "--data-dir"
      - "C:\\Users\\<you>\\.biopipe\\studio\\workspace\\.studio"
      - "mcp"
      - "--allow-run"
```

- `--allow-run` 才允许 agent 提交运行；只读调试去掉它，加 `--read-only` 连编辑也禁止。
- `--workspace`/`--data-dir` 必须与 Studio 的启动参数一致。
- 修改后重启 DSH 与 Studio 生效；在 DSH 里让 agent 调 `biopipe_operator_search` 验证。

其他 MCP 客户端（Cursor、Claude Desktop 等）用等价的 `mcpServers` JSON：

```json
{"mcpServers":{"biopipe":{"command":"biopipe","args":["mcp","--allow-run"]}}}
```

### 在 DeepSeek Harness 中选择工作区与权限

| 项 | 建议 | 说明 |
| --- | --- | --- |
| 工作区 | BioPipe 代码目录（如 `D:\BioPipe`）；只做数据分析时可用专用数据目录（如 `D:\biopipe-work`） | agent 会读写该目录；不要把 `C:\Windows`、`C:\Program Files`、盘符根目录或整个用户目录设为工作区 |
| 文件权限 | 保持默认的 workspace-write | 只允许写工作区与临时目录；不要为常规分析开启 danger-full-access |
| MCP 权限 | `mcp --allow-run` | 允许发现算子、校验并提交运行；只读排查时去掉该参数，禁止编辑时再加 `--read-only` |
| 插件 | 默认不加 | 只有明确安装受信插件时才加 `--allow-plugins` |

- `--workspace` 与 `--data-dir` 必须指向同一套 Studio profile，否则 agent 看到的路线与画布不一致。
- 画布协作时，先让 agent 调用 `biopipe_context` 读取当前选区；无画布（headless）时可直接提交 workflow，不需要伪造会话。
- 数据集与产物放在工作区内；不要把 `.studio`、`tasks`、私钥或凭据放进工作区之外的路径。

### 最小示例提示词

把下面这段直接粘给 DSH，即可验证 MCP 全链路（搜索 → 校验 → 提交 → 查结果）：

```text
用 BioPipe MCP 完成一次最小验证：
1) biopipe_operator_search 查询 "single cell" 相关算子；
2) biopipe_workflow_prepare 校验一个只含读入与一个算子的路线，参数用默认值；
3) biopipe_submit 提交，request_id 固定为 demo-001；
4) 用 biopipe_job 与 biopipe_artifacts 汇报状态和产物。
不要修改任何画布，不要更换参数。
```

若希望 agent 直接操作当前画布，把第 1 步换成 `biopipe_context`（读取选区与 revision），
并明确要求“每次编辑一个事务、不自动运行”。

Studio 的 **Agent 面板** 会按当前解释器和 profile 生成可直接粘贴的配置，并显示已连接客户端。

## 5. 连接你自己的 Agent

把第 4 步的 JSON 放进 agent 客户端的 MCP 配置（Claude Desktop、Cursor、Continue 等
都支持 `mcpServers`）。推荐工作流：

1. `biopipe_operator_search` 找算子；
2. `biopipe_operator_describe` 看 `inputs`/`params`（只取需要的 section）；
3. `biopipe_workflow_save` 保存工作流；
4. `biopipe_workflow_prepare` 校验；
5. `biopipe_submit` 提交运行（需要 `--allow-run`）；
6. `biopipe_jobs` / `biopipe_job` / `biopipe_logs` / `biopipe_artifacts` 跟踪与取结果。

画布相关工具读取用户在 Studio 里的真实选择，按 revision 检查批量应用，每批一个撤销点。
编辑不会自动开始运行；提交是单独动作。

## 6. 连接远程服务器

这一页保存的是“如何 SSH 到那台机器”。连接成功后才会上传源码、准备环境；字段本身不会触发安装。

| 字段 | 含义 | 必填 / 默认 | 示例 |
| --- | --- | --- | --- |
| 名称 | 本机列表里显示的名字，只影响界面 | 必填 | `计算服务器` |
| 主机 | 服务器 IP 或域名（IPv4、IPv6、主机名均可） | 必填 | `172.22.148.93` |
| 端口 | SSH 端口 | 默认 `22` | `22` |
| 用户名 | 登录用的 Linux 账号 | 必填 | `lihj` |
| 服务器环境 | `已安装的 BioPipe 服务端` 由 BioPipe 在服务器用户目录安装/复用托管环境；`手动指定环境` 复用服务器上已有的 BioPipe 代码与解释器 | 默认托管 | `已安装的 BioPipe 服务端` |
| 安装目录 · 可选 | 仅托管模式。托管环境根目录，留空为 `~/.local/share/biopipe`；换目录即全新环境，不复用旧环境 | 可选，绝对路径 | `/public/home/lihj/biopipe-accept` |
| BioPipe 目录 | 仅手动模式。服务器上已有代码根目录（含 `pyproject.toml`、`src/`） | 手动模式必填，绝对路径 | `/opt/biopipe` |
| Python | 仅手动模式。该环境解释器，可为绝对路径或命令名 | 手动模式必填，默认 `python3` | `/opt/conda/envs/biopipe/bin/python` |
| 运行目录 | 远端任务与产物的根目录；托管模式可留空，默认在安装目录下创建 | 手动模式必填，绝对路径 | `/public/home/lihj/biopipe-work` |
| 认证方式 | `密码`、`私钥文件`、`SSH Agent` | 默认密码 | `私钥文件` |
| 密码 | 仅用于本次会话，不写入磁盘 | 密码认证时填 | — |
| 本机私钥路径 | 运行前端那台机器上的私钥文件路径（不是服务器路径） | 私钥认证时填 | `C:/Users/you/.ssh/id_rsa` |
| 私钥口令 | 私钥有口令时填，可留空 | 可选 | — |
| SSH 网关 → 登录方式 | `普通 SSH` 直连；`交互式网关` 用于跳板机/带编号菜单的登录 | 默认普通 | `普通 SSH` |
| 实例编号 | 仅交互式网关：菜单里要选的编号 | 网关模式填 | `0` |

要点：

- 托管模式只需 `主机 / 端口 / 用户名 / 认证`，其余留空即可；首次连接会确认主机指纹，然后上传源码、安装 micromamba 与 Python 依赖。
- 手动模式必须提供 `BioPipe 目录`、`Python`、`运行目录`；BioPipe 不会改动该环境之外的系统路径。
- 更换 `安装目录` 等于新建一套环境；想让新旧互不影响就填不同目录。
- 路径字段必须是绝对 Linux 路径，不允许 `..`；所有字段禁止控制字符，端口范围 `1–65535`。
- 已保存的连接可在“服务端维护 → 安装 / 升级服务端”里重跑安装或升级；断线重跑会复用 `~/.cache/pip`。
- 安装完成后标志是 `env-*/biopipe-ready.json`，日志为 `setup-*.log`；验收测试请用全新目录，避免复用已测环境。

## 7. 编辑画布

- 左侧算子库搜索后拖入画布，连线决定数据流；右侧面板填参数。
- 输入端口接受注册过的 Reader（FASTA、PDB、CSV、10x MTX、PLINK 等）。
- `Ctrl+Z` 撤销；每次拖拽/连线/参数修改都是一个可撤销事务。
- 选择节点后 **Agent → Copy selection context**，可把当前选择发给 agent。

## 8. 发起运行

三种入口，效果一致（同一个应用服务）：

1. **前端**：选中输出节点或整张图，点 **运行**；第一次运行需要确认执行权限。
2. **Agent**：`biopipe_submit`（带 `--allow-run`），再 `biopipe_job` 轮询。
3. **CLI**：

```text
python scripts/run.py <task 目录或工作流 JSON> --check   # 只校验
python scripts/run.py <task 目录或工作流 JSON>           # 真正执行
```

## 9. 查看结果

运行结束在 **Jobs / 运行记录** 里看日志与状态；**Artifacts** 面板按算子输出分组，
可预览表格/图片/结构文件并导出。MCP 用 `biopipe_artifacts` 取同样的产物列表。

## 10. 常见问题

| 现象 | 处理 |
| --- | --- |
| MCP 工具调用被拒绝 | 检查是否加 `--allow-run`；只读模式不能提交 |
| 前端打开是空白 | 先 `npm run build`；开发模式需同时起 `npm run dev` |
| 远程安装卡住 | 看 `~/.local/share/biopipe/managed-v1/setup-*.log`，见 `agent_environment_repair.md` |
| 服务器算子提示缺 openmm/antifold | 按 `agent_environment_repair.md` 安装可选依赖 |
| 端口被占用 | `scripts/studio.py --port 8766` |
| 想隔离实验 | `--profile-dir <name>` + `--workspace <dir>` 同时指定 |

## 11. 从零干净验收（最终测试）

需求：最终验收必须是本地前端从零向服务器发起的一次安装；已测试环境可以保留，但测试
环境必须干净。

1. backend 更新到最新 `D:\BioPipe`（版本号见 `biopipe/__init__.py`）。
2. 选一个全新 base 目录（连接服务器时填写），例如 `~/biopipe-clean-test`，不要复用
   已有 `managed-v1`。也可以保留 base 但删除测试用环境：
   `rm -rf <base>/env-*`（保留 `mamba-cache`、`~/.cache/pip` 可以加速，不影响"干净"）。
3. 确认干净：`ls <base>/env-*/biopipe-ready.json` 不存在，且没有旧 `server.json`
   指向已装环境。
4. 在本地前端连接服务器，观察安装进度；首次下载约 8–12 GB。
5. 通过标志：`biopipe-ready.json` 存在、`pip check` 无输出、日志末尾
   `BioPipe and Hi-C environment ready`。
6. 记录版本、registry 计数、耗时、env 大小与日志尾部，作为验收证据。

注意：不要预先 `register` 环境；手工部署的环境只作为缓存与证据，不参与本次验收。
