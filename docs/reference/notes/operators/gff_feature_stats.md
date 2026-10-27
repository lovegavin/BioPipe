## 审校补充（GFF 特征统计）

- 输入是 GFF3/GTF Reader 的 `[record, field]` Form；按 `type` 分组。
- 统计 count、总长度、平均/最小/最大长度、每 gene 平均 exon 数；长度按 `end-start+1`（1-based inclusive）。
- `gene`/`exon` 识别依赖编码列和属性列；缺少层级时相应统计可能为空。
- 这不是“基因组覆盖率”；覆盖率需先合并区间再除以参考基因组长度。
- 不同注释版本（GENCODE/Ensembl/RefSeq）不要直接混在同一张表比较。
