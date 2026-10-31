# Reader：文件格式到 Form 的适配器

[Reader](../../../src/reader/base.py) 负责把一种外部文件格式读成 [Form](form.md)。
Reader 只做“读取与格式解析”，不做统计建模；它的参数必须是严格 JSON Schema。

## 必须声明

- `extensions`：处理的扩展名（小写，含点）。
- `output_contract`：输出的维度/语义；Runner 会据此校验。
- `parameters_schema`：读取参数；`additionalProperties: false`。
- `read(path, dims, labels, **args) -> Form`。
- 可选 `file_input`：Studio 导入提示（格式、压缩、示例）。
- 可选 `probe`：只读元信息，不把文件字节当内存占用。
- 可选 `read_to_disk`：分块落盘，供大文件流式读取。
- 可选 `requires_siblings` / `excludes_siblings`：同名 sidecar 约束。
- `category`、`title`、`description`、`platforms`：目录/前端/平台标记。
- `handles_compression`：Reader 是否直接消费压缩输入。

## 分派

`pick_reader(path, name=None)` 的顺序：

1. `name` 显式指定 Reader（YAML `args.reader`）；
2. 扩展名匹配；
3. sidecar/压缩条件；
4. 无匹配则报错，不退回“猜一个解析器”。

同一扩展名被多个 Reader 声明时，必须有 sibling 条件或显式 `reader` 区分；否则
注册表检查会报冲突。

## 标签与编码

`labels` 每个维度支持：

- `builtin`：使用格式自带的标签；
- `auto`：位置编号 `"0"`, `"1"`, …；
- `{"sample": 0}`：从数据中取某列/位置作标签；
- `{name: pos, ...}`：显式标签映射。

分类列必须把编码器写入 `info["encoders"] = {dim: {label: encoder}}`，下游
`group_values` 才能还原类别名。

## 平台标记

`platforms=["linux","darwin"]` 表示该 Reader 在原生 Windows 不可用（例如依赖
`pysam`/`pyBigWig`）。前端显示“Windows 不可用”，但任务仍可在 Linux/WSL 运行。
未声明 `platforms` 表示不限制平台。

## 新增 Reader 检查单

1. 文件名不以 `_` 开头，类定义在自身模块中（不要从其他模块 import 后“顺带”发现）。
2. 类名唯一；`name` 与参考页一致。
3. 参数 schema 严格；给默认值；拒绝未知键。
4. 读出的 Form 通过 `validate()`；标签完整；`axis_info` 正确。
5. 至少一个正常 fixture、一个格式负例、一个分派测试；能对照权威实现时加 oracle。
6. 重建 registry，生成参考页，更新索引计数。

相关：Registry 如何发现 Reader 见 [registry.md](registry.md)，SDK 的 Reader 包装见
[sdk.md](sdk.md)。
