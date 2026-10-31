# SDK：作者面向的最小协议

[SDK](../../../biopipe_sdk/) 让第三方在不改 BioPipe 核心的情况下提供算子/Reader/
包。协议版本当前为 `1`；所有公开对象都是 JSON 兼容的 Pydantic 模型。

## 四层对象

1. **Descriptor**：一个算子或 Reader 的公开描述（id、kind、title、category、
   parameters_schema、contracts、platforms、dependencies）。
2. **PackageDescriptor**：一个安装单元，包含若干 descriptors。
3. **Operator**：继承 [Step](step.md)，实现 `compute(inputs, params, context)`；
   返回 Form 或 report。
4. **Reader**：继承 [reader.md](reader.md) 的基类，实现 `read`，声明扩展名/契约。

## 参数与契约

- `parameters_schema` 必须是自包含的 JSON Schema（object 根、`additionalProperties:
  false`、只允许本地 `$ref`）。
- 参数默认值由 `validate_parameters` 补齐；YAML 的科学计数法字符串只在 schema 声明为
  number/integer 时转换。
- `contracts` 描述 inputs/output；Runner 会在执行前后校验，不是装饰性文档。
- `platforms` 缺省表示所有平台；原生 Windows 不可用的实现应显式标注。

## 依赖与打包

- `dependencies` 是 PEP 508 列表；兼容版本共享宿主环境，冲突版本走私有依赖目录。
- `dependency_imports` 可选，用于导入烟雾检查。
- entry point 指向类；包构建后由 Registry 校验 descriptor 与实现一致。
- 公开 schema 文件在 `biopipe_sdk/schemas/`，必须与模型同步（测试会逐字节比较）。

## 测试辅助

`biopipe_sdk/testing.py` 提供参数/契约断言辅助；作者至少应覆盖正常 fixture、边界、
非法参数，以及与权威实现对照（若可用）。

## 兼容边界

- 内置算子可以直接继承 Step 以使用多输出/流式等能力；SDK 的 Operator 是简化层，
  不是另一套执行引擎。
- 自定义分类在 SDK/源码库层允许；进入内置清单时归一化为六类。
- 展示字段（category、description、icon、platforms）不参与 wheel 与实现的执行语义
  比较；执行字段仍要求精确一致。

相关：Registry 如何收集/校验见 [registry.md](registry.md)，Reader 细节见
[reader.md](reader.md)。
