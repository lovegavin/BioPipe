## 审校补充（GFF3）

- 9 列、1-based inclusive；`start/end` 与 BED 的 0-based half-open 不同。
- `##FASTA` 之后是序列，不是注释；Reader 在这里停止，避免把序列当记录。
- `attributes` 是分号键值对；`ID`/`Parent` 关系用于 gene/transcript/exon 层级。
- 注释行的 `#` 不是数据；`##sequence-region` 等指令要跳过。
- 大文件建议先按 chromosome/feature type 子集，避免下游全量聚类。
