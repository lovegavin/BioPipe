# 用户手册：用 LLM 搭建 BioPipe 任务

本手册给不使用/不熟悉仓库代码的用户。你只需要准备数据、把绝对路径交给 LLM、审阅并运行它生成的任务。

BioPipe 的目标是让 LLM **调用已验证的算子**，而不是每次临时写分析代码；这能减少实现错误和不必要的 token 消耗。完整定位见 [价值主张](vision.md)。

## 1. 准备环境（Windows PowerShell）

在项目根目录：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[agent,dev]"

cd frontend
npm install
npm run build
cd ..
```

如果 PowerShell 禁止激活脚本：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Node 需要 22.12+。前端构建只需做一次；前端代码未改时不必反复构建。

## 2. 新建任务目录

```text
tasks\<任务名>\
  input\
```

把数据放进 `input/`。文件名保持简单，避免空格/中文路径引起终端转义问题；如果原始文件很大，可以复制或做硬链接。

## 3. 给 LLM 的请求

必须提供：

- 数据的**绝对路径**，例如 `<数据目录>\counts.csv`；
- 分析目标（可选）；
- 数据背景（物种/组织/分组/平台，可选但强烈建议）；
- 期望输出（表格/图/差异分析/富集等，可选）。

示例：

```text
项目根目录：<项目根目录>
数据绝对路径：<数据目录>\airway_counts.csv 和 <数据目录>\airway_meta.csv
目标：比较 dex 和 untrt 两组，找差异基因，画火山图和热图。
请按 docs/route_sop.md 和 docs/llm_guide.md 操作：
先 inspect 数据，再读必要算子页，生成 tasks/airway_dex/ 下的 task.yaml 和 ANALYSIS.md，
跑 --check，然后告诉我怎么导入和运行。
```

LLM 应先检查文件并给出数据概况；如果它直接写 YAML、不验证路径，要求它重做。

## 4. 审阅 LLM 的交付物

### `task.yaml`

重点检查：

- `sources.path` 是否指向 `input/` 下的文件；
- `dims`/`labels` 是否符合数据；
- 每个 step 的 `inputs` 是否由前一步或 source 产生；
- 参数是否有依据，不是“适当过滤”；
- 输出名是否唯一；
- 图片文件名是否只是文件名。

### `ANALYSIS.md`

重点检查：

- 绝对路径和实际落盘路径是否写清；
- 每一步为什么做、参数值从哪来；
- 过滤掉了多少；
- 每张图怎么读、不能说明什么；
- 有没有把相关性/未校正 P 值说成因果/显著。

## 5. 静态检查

在项目根目录：

```powershell
python scripts/run.py tasks\<任务名> --check
```

必须看到：

```text
"ok": true
CHECK OK
```

`--check` 不会执行分析。它只检查文件、Reader、参数、输入输出和图片名。失败时把完整错误交给 LLM 修，不要直接运行。

## 6. 运行

### 命令行

```powershell
python scripts/run.py tasks\<任务名>
```

### Studio

1. 启动 Studio：`python scripts/studio.py`；
2. 打开 `http://127.0.0.1:8765`；
3. 使用“导入 YAML / JSON”，选择 `tasks\<任务名>\task.yaml`；
4. 检查源文件路径和参数；
5. 运行。

如果 Studio 提示找不到输入文件：新版会先按 YAML 的 `name` 查找同名任务目录，再按唯一相对路径自动定位；若同名文件有多个候选，才需要在导入框填写“YAML 输入相对目录”。

自动定位后，检查器里显示的输入路径可能是解析后的绝对路径；这是正常的。导出 YAML 时会按任务目录重新写成相对路径。

如果自动定位仍不符合预期，可以直接在 YAML 的 `sources.*.path` 写项目内绝对路径；`tasks/user_ml_age/task.absolute.yaml` 是一个可直接导入的示例。

重新选择一个输入文件时，已有 source 的 dims/labels/Reader 参数会保留，只替换路径；如果换成了不同格式，请手动清空不再适用的 Reader 参数。

## 7. 结果在哪

```text
tasks\<任务名>\output\
  run_summary.txt / run_summary.json
  figures\*.png
```

运行日志在终端输出；Studio 里看 Run logs。

## 8. 常见错误

| 错误 | 处理 |
|---|---|
| `file not found` | 检查 `input/` 和 YAML 相对路径 |
| `No reader for extension` | 让 LLM 查 Reader 索引；必要时指定 `args.reader` |
| `Additional properties are not allowed` | 让 LLM 删掉未知参数/`_input_names` |
| `heatmap ... max_cells` | 矩阵太大：用 `select/top_n`、子集或先聚合 |
| 图片内存不足 | 降低 `max_pixels`、减少行列、关闭聚类 |
| `contract incompatible` | 让 LLM 检查 dims/labels/编码 |

## 9. 数据与隐私

- BioPipe 本地运行，不上传数据；
- 只有你主动把数据/图片交给外部 LLM 时，数据才会离开本机；
- 不要把患者标识、密钥或不必要的原始数据发给外部模型；
- 大文件先脱敏/抽样，再让 LLM 检查结构。

## 10. 参考

- [任务 SOP](route_sop.md)
- [LLM 手册](llm_guide.md)
- [算子/Reader 索引](reference/README.md)
- [ANALYSIS 模板](templates/ANALYSIS.md)
- [固定提示词](prompts/route_architect.md)
