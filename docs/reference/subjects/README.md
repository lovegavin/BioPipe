# 系统对象（Subjects）

这里不是算子和 Reader 的逐项参数表；那部分在
[算子索引](../operator_index.json)、[Reader 索引](../reader_index.json)和各自的
`operators/`、`readers/` 页面。本目录解释 BioPipe 中九个**长期存在的系统对象**：
它们各自负责什么、边界在哪里、修改时必须保持哪些不变量。

| 对象 | 一句话职责 | 页面 |
| --- | --- | --- |
| Form | 唯一的内存数据载体：张量 + 维度名 + 标签 + 元信息 | [form.md](form.md) |
| Task | 一个可检查、可复现的任务目录与 `task.yaml` | [task.md](task.md) |
| Graph | Studio 中的有向工作流，可导入/导出为 Task | [graph.md](graph.md) |
| Project | 相对路径、项目根目录和文件访问边界 | [project.md](project.md) |
| Reader | 把外部文件读成 Form，并声明格式/参数/平台 | [reader.md](reader.md) |
| Step | 算子契约：输入、参数、输出、执行和导出 | [step.md](step.md) |
| Runner | 按 DAG 顺序执行步骤，做契约/参数/输出检查 | [runner.md](runner.md) |
| Registry | 从源码发现扩展，生成内置包清单并做完整性检查 | [registry.md](registry.md) |
| SDK | 作者面向的最小协议：Descriptor、Operator、Reader、包 | [sdk.md](sdk.md) |

## 建议阅读顺序

- **只写任务**：task → form → runner。
- **新增算子**：step → registry → sdk。
- **新增 Reader**：reader → form → registry。
- **排查 Studio 导入/路径**：graph → project → task。
- **做插件/打包**：sdk → registry → project。

## 维护规则

1. 这九页是人工维护的架构说明；算子/Reader 的参数页由
   `scripts/build_reference_docs.py` 生成。
2. 修改这些对象的公共行为时，必须同步本页和对应的源码/测试链接。
3. 页面只写可验证的事实；数字和示例应能在仓库中复现。
