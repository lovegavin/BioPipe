# Project：项目根、相对路径与访问边界

BioPipe 把“项目根目录”（project root）作为所有用户数据的边界。Task 目录、route
目录、Studio 工作区都相对于它解析；外部文件必须先进入项目（通常是
`tasks/<name>/input/`）才能被任务引用。

## 路径规则

1. `task.yaml` 中的 source `path` 相对**任务目录**，不是当前 shell 目录。
2. Graph 中的 source `path` 相对 `Graph.base_dir`；导入时由后端解析。
3. 导出/保存时路径应保持相对形式；绝对路径会降低可移植性，并在检查/导入时被限制。
4. `project_path(root, path, base)` 负责把相对路径解析到项目内，并拒绝 `..`、盘符、
   绝对路径等逃逸形式。
5. 输出文件名只能是单段文件名；Runner 会拒绝带目录/盘符的 `filename`。

## 自动定位 Task

导入 YAML 时，如果未显式给 `base_dir`，后端会尝试：

- YAML 的 `name` 是否唯一匹配 `tasks/<name>` 或 `routes/<name>`；
- 否则在 `tasks/`、`routes/`、`examples/` 下寻找唯一的相对路径匹配；
- 多个候选时拒绝猜测，要求用户填写“YAML 输入相对目录”。

这样用户把任务文件夹整体放到 `tasks/<slug>/` 后，导入 YAML 不必手工填绝对路径。

## 目录边界

- `tasks/<slug>/input/`：用户数据；不要在这里放大体量临时输出。
- `tasks/<slug>/output/`：运行产物；由 Runner 创建/覆盖。
- `routes/`：可复用工作流模板；路径必须相对，才能跨机器导入。
- `docs/`、`src/`、`tests/`：代码/文档，不是任务数据目录。

## 常见失败

- 在 YAML 写 Windows 盘符绝对路径或 Linux 用户目录绝对路径：换机器/换挂载点后失效。
- `base_dir` 指到任务目录之外：被项目边界检查拒绝。
- 用 `..` 访问兄弟任务：被拒绝；应把共享数据放到项目内明确位置。
- 把 Windows 路径分隔符写进输出名：Runner 拒绝。

相关：Task 目录结构见 [task.md](task.md)，Graph 的 `base_dir` 见 [graph.md](graph.md)。
