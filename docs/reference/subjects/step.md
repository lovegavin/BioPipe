# Step：算子的执行契约

[Step](../../../src/task/step/base.py) 是算子的基类。一个算子声明“需要几个输入、
接受哪些参数、产生什么输出、如何执行/导出”，Runner 负责在运行时检查这些声明。

## 类属性

| 属性 | 作用 |
| --- | --- |
| `name` | 唯一算子 id；YAML 的 `steps[].name` |
| `title` | 人类可读名称 |
| `category` | 六类之一：Data / Statistics / Machine Learning / Omics / Visualization / Quality Control |
| `builtin_package` | 归属内置包；影响 registry 所有权 |
| `inputs_arity` | 输入个数；`"*"` 表示至少一个 |
| `outputs` | 注册到 Context 的输出名列表 |
| `output_parameter` | 用参数指定输出名的键（通常是 `output`） |
| `input_contracts` | 每个输入的维度/语义要求 |
| `output_contract` | 输出契约；可为 `{"mode": "report"}` |
| `parameters_schema` | 严格 JSON Schema；禁止未知参数 |
| `supports_streaming` | 是否支持分块流式执行 |
| `version` / `dependencies` | 版本与依赖声明 |

## 执行协议

```python
class MyStep(Step):
    name = "my_step"
    inputs_arity = 1
    output_parameter = "output"
    parameters_schema = {...}
    input_contracts = [{"dims": ...}]
    output_contract = {"dims": ...}

    def run(self, ctx, inputs):
        ctx[ctx.step_params["output"]] = result_form

    def export(self, ctx):
        return {"summary": ...}
```

- `run` 必须把声明的每个输出注册进 `ctx`；少注册会被 Runner 拒绝。
- `export` 返回可 JSON 序列化的完整结果；不要截断。
- 报告型算子设置 `output_parameter=None`、`output_contract={"mode":"report"}`，不注册 Form。
- `parameters_schema` 的默认值会在运行时补齐；未知参数直接报错。
- `run` 抛出的 `StepError` 会终止任务并把状态标为 failed。

## SDK 的简化层

作者通常继承 [Operator](../../../biopipe_sdk/operator.py)，实现
`compute(inputs, params, context)` 并返回一个 Form 或 report；SDK 负责把结果注册到
Context。需要多输出/流式/底层控制时再直接继承 Step。

## 测试要求

- 正常 fixture：断言数值、形状、标签、info。
- 边界/负例：非法参数、空数据、维度不匹配、常数/秩亏等。
- 能对照 R/Python/CLI 权威实现时，加 oracle 测试并记录容差。
- 新算子必须被 Registry 发现并由 catalog-integrity 测试覆盖。

相关：Runner 如何调用 Step 见 [runner.md](runner.md)，Registry 如何生成描述见
[registry.md](registry.md)。
