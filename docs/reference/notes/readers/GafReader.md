## 审校补充（GAF）

- 17 列固定，`!` 开头为注释；`db_object_synonym` 是管道分隔多值，放在 `info` 而非 data。
- GO 注释是“基因-术语”对，不是表达矩阵；下游通常 `pivot`/`enrich_go`。
- 不要直接按行数当基因数；一个基因可有多行/多术语。
- 大 GAF 读取慢，先确认 taxon/aspect 过滤需求。
