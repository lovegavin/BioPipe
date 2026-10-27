## 审校补充（TSV）

- 默认制表符分隔，其余行为与 CsvReader 一致（header/columns/encoders/缺失）。
- 不要用逗号分隔的 `.tsv` 而不指定 `sep`；Reader 不会自动猜。
- 非数值列编码；下游按标签对齐。
- `.tsv.gz/.bz2/.xz` 由 framework 解压。
