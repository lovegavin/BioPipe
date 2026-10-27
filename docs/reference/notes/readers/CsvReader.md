## 审校补充（CSV）

- 默认逗号分隔；制表符文件必须显式 `sep: "\t"`，不要假设自动嗅探。
- `header: true` 时第一行是列名；`columns`/`info_columns` 可抽取/声明列；非数值列编码进 `info["encoders"]`。
- 缺失标记默认识别为 NaN；空字符串/`NA` 的处理由参数决定，需在 ANALYSIS 说明。
- `.csv.gz/.bz2/.xz` 由 framework 解压到临时文件；Reader 看到的是普通 CSV。
- `reader: csv` 是路由选择器，不是 Reader 参数；`--check` 会剥离它。
