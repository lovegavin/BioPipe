# Registry：扩展发现与内置包清单

[Registry](../../../biopipe/registry.py) 把源码中的 Step/Reader 声明收集成
`biopipe/builtin_packages.json`，供前端、文档、检查和安装使用。它是**显式维护**
产物：不在 Studio 启动时自动重写。

## 清单结构

- `packages[]`：一个安装单元（内置包或 wheel）。
- 每个 package 有 `name`、`version`、`origin`、`descriptors[]`。
- 每个 descriptor 是 [SDK](sdk.md) 的 `Descriptor`：id、kind、title、category、
  parameters_schema、contracts、platforms 等。
- 路由清单在 `src/web/builtin_routes.json`；算子/Reader 索引在
  `src/task/operator_ui.json` 与参考页。

## 发现规则

`scan_sources()` 扫描：

- `src/task/step/steps/*.py`（不以 `_` 开头）
- `src/reader/readers/*.py`（不以 `_` 开头）

只接受**定义在自身模块**中的类；从其他模块 import 进来的类不会重复注册。
每个类必须有 `parameters_schema`（内置兼容算子可走 legacy adapter）、唯一 id；
Reader 还必须有扩展名和输出契约。重复 id、缺 schema、导入失败都会进入 errors，
不会静默覆盖。

## 分类与展示元数据

- 内置包强制六类规范名：Data、Statistics、Machine Learning、Omics、Visualization、
  Quality Control；`build_catalog(..., normalize_categories=True)` 负责归一化。
- 自定义插件/源码库可保留作者分类（`normalize_categories=False`）；前端把别名映射到
  规范类，未知值落入 Other。
- Reader 的 `category`、`title`、`description`、`platforms` 来自类属性/文档字符串；
  缺失时由 `describe_reader` 给安全回退。

## 常用命令

```bash
BIOPIPE_REGISTRY_MAINTENANCE=1 python -m biopipe registry build
BIOPIPE_REGISTRY_MAINTENANCE=1 python -m biopipe registry check
python scripts/build_reference_docs.py
```

`build` 会写清单并校验包结构；`check` 只校验。参考页必须与算子/Reader 计数一致。

## 自动检查

- `tests/test_catalog_integrity.py`：源码发现的 id 集合必须等于清单；每个内置
  descriptor 的分类合法、标题/描述非空、schema 为 object；Reader 扩展名存在。
- `tests/test_reference_docs.py`：每个算子/Reader 有参考页，索引计数一致。
- 前端测试：清单中的全部算子/Reader 都能展示，分类规范、描述非空、平台标记传播。

因此新增扩展不能只“文件存在”：必须能被发现、进清单、有文档、通过完整性测试。

相关：Reader 契约见 [reader.md](reader.md)，Step 契约见 [step.md](step.md)，SDK 见
[sdk.md](sdk.md)。
