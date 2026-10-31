# Form：唯一的内存数据对象

[Form](../../../src/core/forms/form.py) 是算子之间传递数据的唯一结构。一个 Form
就是“带命名的多维张量”：没有表头、没有隐藏的 DataFrame 列，也没有第二套行/列对象。

## 结构

```python
Form(
    data=np.ndarray,          # 纯数值张量
    dims=["sample", "feature" ],
    labels={"sample": {"S1": 0}, "feature": {"G1": 0}},
    info={"source": "..."},
    axis_info={"sample": ["batch"]},
)
```

- `data.ndim == len(dims)`，且 `dims` 不重复。
- 每个维度的每个位置都必须有**唯一标签**；`validate()` 会拒绝缺标签、重复位置、
  越界位置。
- `info` 保存非数组元信息（来源、方法、阈值、`encoders` 等）。
- `axis_info` 声明哪些 `info` 数组与某个轴平行；`subset_axis` 只裁剪这些数组，
  不靠“长度猜”。

## 必须保持的不变量

1. 数值 dtype 由生产者负责；跨算子比较时显式转换，不依赖隐式副本。
2. 轴顺序有意义；需要交换/转置时使用算子，不在调用方手工改 `dims`。
3. 标签是数据的一部分；过滤后必须同步裁剪标签和声明过的 `axis_info`。
4. 分类列用 `info["encoders"]` 记录编码器，输出时才能还原类别名。
5. 不要把文件路径、DataFrame、第三方对象塞进 `data`；它们属于 `info` 或 Reader。

## 常用操作

- `form.axis("sample")`：取轴序号。
- `form.get_parallel("batch", "sample")`：取与轴平行的数据列或 `info` 数组。
- `form.subset_axis("sample", indices)`：返回新 Form，标签和 `axis_info` 同步裁剪。
- `form.validate()`：写入 Context 前、Reader 返回后、测试断言时调用。

## 常见错误

- `len(dims) != data.ndim`。
- 只改了 `data`，没改 `labels`。
- 把 `axis_info` 里的数组当普通 `info` 修改长度。
- 在 `info` 中放不可 JSON 序列化的对象，导致 `run_summary` 写出失败。

相关：Reader 如何产生 Form 见 [reader.md](reader.md)，Runner 如何校验见
[runner.md](runner.md)。
