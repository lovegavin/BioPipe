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

## 4. 连接 MCP

MCP 是"给 agent 用的接口"，不是模型本身。最小配置（单独 profile）：

```json
{"mcpServers":{"biopipe":{"command":"biopipe","args":["--profile-dir","~/biopipe-v3-test","mcp","--allow-run"]}}}
```

- 去掉 `--allow-run`：只能读和准备，不能提交运行。
- 加 `--read-only`：连画布编辑也禁止。
- 加 `--allow-plugins`：允许安装本地 wheel 插件。

Studio 里 **Agent 面板** 会用当前解释器和 profile 生成可直接粘贴的配置，并列出已连接
客户端、可撤销 token。配置改完后重启 agent 客户端。

验证：让 agent 调用 `biopipe_operator_search`（返回算子摘要，不加载实现），再调用
`biopipe_operator_describe` 取契约与参数 schema。

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

进入 **执行环境 / 服务器** 页面，新建 SSH 连接：

| 字段 | 示例 |
| --- | --- |
| 主机、端口、用户名 | `172.22.148.93`、`22`、`lihj` |
| 认证 | 密码、本地私钥文件或 SSH Agent |
| 网关 | 默认普通 SSH；有编号菜单时选交互式网关 |

连接后会校验主机指纹，上传与桌面端匹配的源码，并在服务器上准备独立环境
（micromamba + Python 3.11 + pip 依赖），不需要 root、Conda 或编译器预装。
环境目录：`~/.local/share/biopipe/managed-v1/`（或连接时指定的 base），
日志 `setup-*.log`，完成标志 `env-*/biopipe-ready.json`。

首次安装需要下载约 8–12 GB 的 Python 依赖（PyTorch 等），上行 1–3 MB/s 时
约 1–2 小时；断线重跑会复用 `~/.cache/pip`，之后连接直接复用已有环境。服务器上
`openmm`/`pdbfixer`（MD/能量算子）与 `antifold`（NumPy 1.26 冲突）是可选附加，
未安装时算子会给明确提示，不影响其余流程。

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
