## 审校补充（GTF）

- 9 列、1-based inclusive；属性是 `key "value";` 形式，不是 GFF3 的 `key=value`。
- `gene_id`/`transcript_id` 是层级关键；`feature` 列常为 gene/transcript/exon。
- 与 GFF3 共用读取基类，但属性解析不同；不要混用两种文件的属性假设。
- 坐标/链方向要保持原样；负链基因的区间仍是 start<end（1-based）。
