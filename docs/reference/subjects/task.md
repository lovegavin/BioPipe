# Task：一个可检查、可复现的任务

Task 是 BioPipe 的最小执行单元：一个目录，里面有 `task.yaml`，通常还有 `input/`
和运行后生成的 `output/`。Task 只描述“读什么、按什么顺序算什么”，不保存运行时
对象。

## 目录约定

```text
tasks/<task-name>/
  task.yaml
  input/            # 数据文件；YAML 里写相对本目录的路径
  output/           # 运行时生成
```

`task.yaml` 中的 `path` 是**相对任务目录**的路径，不是绝对路径；这使任务可以整体
移动、复制到 Windows 或 WSL。项目根目录与路径边界见 [project.md](project.md)。

## 最小结构

```yaml
name: example
sources:
  expr:
    path: input/expression.tsv
    dims: [sample, feature]
    labels: {sample: auto, feature: builtin}
    args: {reader: tsv}
steps:
  - name: describe
    inputs: [expr]
    params: {output: summary}
```

- `sources` 必须非空；每个 source 需要 `path`、`dims`，可选 `labels`、`args`。
- `steps` 必须非空；每步需要 `name`，`inputs` 是之前已产生的 Form 名。
- `params` 必须来自该算子的 `parameters_schema`；禁止写 schema 外参数。
- 不写 `_input_names`；它是 Runner 的内部键，导入/运行时会剥离。
- `args.reader` 可显式指定 Reader；否则按扩展名和 sibling 规则分派。
- 输出名由 `params.output`（若算子有）或算子声明决定；不要与已有 Form 重名。

## 检查与运行

```bash
python scripts/run.py tasks/<task-name> --check
python scripts/run.py tasks/<task-name>
```

`--check` 只做静态检查：文件存在、Reader 参数、source dims、输入是否已产生、
算子参数、输出重名、`filename` 是否越界；它**不读取数据、不执行算子**。真正运行时
才由 [Runner](runner.md) 读取 source、执行 Step、写 `output/`。

## 常见失败

- 路径写成绝对路径：移动到其他机器后失效。
- `params` 拼错或出现未知键：严格 schema 会拒绝。
- 输入名指向尚未产生的 Form：检查阶段即报错。
- `filename` 带目录/盘符：输出路径逃逸检查会拒绝。
- 直接改 `output/` 再重跑：输出会被覆盖；应保留输入和 YAML 作为可复现来源。

## 相关对象

Task 是文本形态；Studio 的编辑对象是 [Graph](graph.md)。Graph 可导入为 Task，
Task 也可被 Studio 导入。执行细节见 [runner.md](runner.md)。
