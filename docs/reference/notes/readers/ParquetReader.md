## 审校补充（Parquet）

- 列名来自 Parquet metadata，没有 header 行；`header` 参数不存在。
- 文件自带 index 时作为第一列；需要区分 index 和普通列。
- 非数值列编码进 `info["encoders"]`；数值列保持原 dtype/精度。
- Parquet 内部压缩由 pyarrow 处理；外部 `.gz` 由 framework 解压。
- 读取是整表载入；超大 Parquet 先选列/行子集。
