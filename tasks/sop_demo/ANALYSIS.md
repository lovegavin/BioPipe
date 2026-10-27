# 分析说明：sop_demo

## 1. 数据

| 项目 | 值 |
|---|---|
| 用户提供的绝对路径 | `<原始数据绝对路径>` |
| 落到任务目录 | `input/test_party_1.csv` |
| 为什么这样处理 | 绝对路径用于定位；YAML 用相对路径，保证任务可移动/可导入 |
| Reader / 格式 | `CsvReader` / CSV |
| shape | 41 × 10（运行前由 inspect 确认） |
| dims | `sample, feature` |
| labels | sample=auto；feature=builtin |
| 缺失 | 0（运行前由 inspect 确认） |
| 编码/特殊值 | 无 |
| 配套文件 | 无 |

## 2. 目标与成功标准

- 用户目标：演示如何用 LLM + 说明书搭建一条可校验的最小路线。
- 成功标准：`--check` 通过；PCA 生成 3 个主成分；热图 PNG 非空；能解释每步原因。
- 不在范围内：生物学结论；这是流程演示，不是研究结论。

## 3. 步骤

| # | 算子 | 参数 | 输入 → 输出 | 为什么 |
|---|---|---|---|---|
| 1 | `describe` | 无 | `table` → report | 先记录输入 shape/缺失/范围，作为基线。 |
| 2 | `pca` | `dim=feature, n_components=3` | `table` → `pcs` | 用 3 个主成分压缩 10 个数值特征，便于观察样本结构；仅用于演示。 |
| 3 | `describe` | 无 | `pcs` → report | 检查 PCA 输出维度和数值范围。 |
| 4 | `heatmap` | `select=variance, top_n=10, cluster_*=false` | `table` → PNG | 展示前 10 个方差最大的特征；不聚类以便直接按标签读图。 |

## 4. 图片

| 文件 | 画的是什么 | 轴/单位 | 颜色/阈值 | 怎么读 | 不能说明什么 |
|---|---|---|---|---|---|
| `figures/top_features.png` | 样本 × 前 10 个特征的值 | x=样本；y=特征；颜色=原始数值 | 默认发散色；无数值阈值 | 看样本间颜色块是否相似 | 不能说明分组差异、因果或统计显著性；样本标签是自动生成的。 |

## 5. 假设与限制

- 该文件是演示数据，列名 `x0..x8,y` 没有生物学含义。
- 没有分组、批次、协变量；不能做差异分析。
- PCA 未标准化；数值量纲不同会影响主成分。
- 这是探索性流程演示，不是确证性分析。

## 6. 复现

```bash
python scripts/run.py tasks/sop_demo --check
python scripts/run.py tasks/sop_demo
```
