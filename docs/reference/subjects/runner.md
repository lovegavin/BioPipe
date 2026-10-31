# Runner：按顺序执行并检查契约

[Runner](../../../src/task/runner.py) 接收 [Context](../../../src/task/context/base.py)
和已解析的 steps 列表，逐个执行。它不负责“理解科学含义”；它负责顺序、输入解析、
参数校验、契约校验、输出登记、日志与导出。

## 执行流程

1. `Context` 加载/惰性注册 sources；Reader 在首次使用时读取。
2. 对每一步按 YAML 顺序：
   - 查 `STEPS` 中的算子类；未知算子立即失败。
   - 检查 `inputs_arity`。
   - 合并全局 `params` 与步骤 `context_params`，剥离内部 `_input_names`。
   - 按 `parameters_schema` 校验并填默认值（`legacy_parameters` 算子除外）。
   - 解析输入 Form；校验 `input_contracts`。
   - 推断/校验 `output_contract`；执行 `run`。
   - 确认声明的输出都已注册；写 `output/steps/NN_<name>.json`。
3. 全部完成后写 `output/run_summary.json` 和 `run_summary.txt`。

任何一步抛异常：状态置为 failed，记录错误，停止后续步骤；已完成步骤的产物保留，
便于定位。

## 输入/输出契约

- `input_contracts` 按端口匹配；少于输入数的规则会复用最后一条。
- `output_contract` 可为 `Form` 形状/维度/值域约束，或 `report` 模式。
- `subset_axis`/类型不匹配等问题在这里变成可读的 `StepError`，而不是下游崩溃。

## 内存与取消

- 开启 memory 时，Runner 让 `MemoryRuntime` 准备/落盘输入，并在步骤成功/失败时
  finish/abort；未开启时直接持有 Form。
- 每步开始前检查任务目录下的 `cancel.requested`；存在则抛“Run cancelled by user”。

## 与 `--check` 的区别

`--check` 只做静态检查（文件、Reader 参数、输入顺序、schema、输出重名、文件名），
不读数据、不执行算子。Runner 才真正读文件、计算、写输出。因此“check 通过”不等于
“数值成功”，还需要运行和测试。

相关：算子契约见 [step.md](step.md)，Form 校验见 [form.md](form.md)，任务结构见
[task.md](task.md)。
