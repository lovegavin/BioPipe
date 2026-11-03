# Agent 开场须知

你通过 MCP 连接 BioPipe Studio。只使用 `biopipe_*` 工具，不需要 shell、SSH 或仓库源码。

## 第一轮

1. `biopipe_status()`：确认连接、权限、版本与工作区。
2. `biopipe_sessions()` 后 `biopipe_context(session_id)`：读取画布、选区和当前 `revision`；
   需要整图时用 `scope="document"`。
3. `biopipe_operator_search` / `biopipe_operator_describe`：选算子，只读需要的 schema 与文档段落。

然后等待用户提出分析需求；不要自行开始运行。

## 画布规则

- 只用 `biopipe_apply` 加 `expected_revision` 编辑；一次连贯修改一个事务，绝不替换工作区。
- 想把设计好的图放到用户当前标签页：`biopipe_open(session_id, expected_revision, graph, document_id=...)`；
  `mode="replace"` 覆盖、`"append"` 新开。汇报返回的 `{document_id, revision}`。
- 整图替换用 `biopipe_apply` 的 `{op:"set_graph", graph}`。
- 切换执行设备也是画布编辑：`biopipe_set_execution(session_id, document_id, expected_revision, {kind:"ssh", profile_id:...})`。
- 用户同时编辑会返回冲突和新 revision：重新读上下文再应用，不要静默覆盖。

## 运行

- 只有用户明确确认后才运行。
- 远程设备先 `biopipe_remote_status()`，必要时 `biopipe_remote_ensure(profile_id)`，再 prepare/validate/run。
- `biopipe_workflow_prepare` → `biopipe_validate` → `biopipe_run`（画布）或 `biopipe_submit`（headless）。
  `request_id` 仅用于相同请求的重试。
- 任务在主机准入额度内并行；`biopipe_jobs` 查看列表，`biopipe_job` 查看单个。
- 结果：`biopipe_artifacts` 看索引，`biopipe_artifact_table` 取分页带标签表格（本地与 ssh 任务都支持），
  `biopipe_logs` 看控制台输出。Studio 里能看到的，MCP 都能拿到，无需下载即可总结。

## 汇报

- 使用用户的语言；先汇报节点、边、参数、设备与数据路径，再请求确认。
- 数字要带来源：artifact id、列名、行标签。
- 缺依赖时引用任务错误与资源清单的安装建议，绝不编造结果。
