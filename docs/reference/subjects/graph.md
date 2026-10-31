# Graph：Studio 中的工作流

[Graph](../../../src/web/models.py) 是 Studio 的内存/保存格式：节点、边、参数、
source 声明、route 接口和布局。它不是 Runner 的直接输入；运行前会转换成
`task.yaml` 并交给 [Task](task.md) / [Runner](runner.md)。

## 结构

- `source` 节点：声明文件路径（相对 `base_dir`）、`dims`、`labels`、`args`。
- `operator` 节点：引用算子名、参数、`context_params`、`input_count`。
- `route` 节点：嵌套一个可复用的子工作流。
- `edges`：从 `out` 到 `in-0`、`in-1`……必须形成 DAG。
- `base_dir`：所有 source 相对路径的解析基准。
- `interface`：route 的输入/输出契约；用于嵌套时校验。
- `memory`、`params`、`runtime`、`manifest_extra`：传入 Task 的附加配置。

节点 id 是稳定标识（字母/下划线开头），不是显示标题；改标题不应改 id。

## 导入与导出

- 导入 Task YAML：解析 sources/steps、按 `base_dir` 找文件、自动布局、生成 Graph；
  可按 YAML 的 `name` 自动定位 `tasks/<name>` 或唯一路径。
- 导出 Task YAML：按拓扑顺序写回 sources/steps；路径保持相对 `base_dir`。
- 不合法图（环、类型不匹配、接口不闭合、参数未知）在导入/保存时拒绝，不等到运行。

## 与 Task 的边界

Graph 可以携带布局、viewport、插件锁等 UI/工作区信息；Task 只保留可复现的执行
语义。不要把 viewport、选中状态写进 `task.yaml`；也不要把运行时 Form 放进 Graph。

## 常见失败

- source 路径相对了错误的 `base_dir`。
- 多个同名 task 导致自动定位歧义；应显式填写导入目录。
- 手改边但没改 `input_count`/接口，导致嵌套 route 契约不匹配。
- 用显示标题当节点 id，重命名后连线断裂。

相关：Project 路径规则见 [project.md](project.md)，Registry 如何验证算子见
[registry.md](registry.md)。
