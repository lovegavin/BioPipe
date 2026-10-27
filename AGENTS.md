# AGENTS.md

本仓库的 Agent 规则：

1. 不要通读整个仓库。先读 `docs/route_sop.md` 和 `docs/llm_guide.md`。
2. 先用 `docs/reference/operator_index.json` / `reader_index.json` 筛选，再只读候选页面和必要的源码/测试。
3. 用户必须提供数据绝对路径；先验证存在，再复制/硬链接到 `tasks/<slug>/input/`。
4. `task.yaml` 只写相对任务目录的路径，不写绝对路径。
5. 不写 `_input_names`；它是引擎内部键。
6. 不写 schema 外参数；参数必须来自算子页面/`--check`。
7. 写完 YAML 必须运行 `python scripts/run.py tasks/<slug> --check`，通过后再让用户运行。
8. 写 `ANALYSIS.md`：绝对路径 → 相对路径、数据概况、逐步理由、图片说明、假设/限制。
9. 不编造数据或结论；图片只描述能支持的内容。
10. 不改前端；前端由用户测试。
