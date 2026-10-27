## 审校补充（TXT）

- `.txt` 没有固定格式；TxtReader 委托 CSV/TSV 解析，必须显式给出 `sep` 或 `reader`。
- 制表符文本建议 `sep: "\t"`；逗号文本用 `reader: csv` + `sep: ","`。
- 不要在未检查分隔符的情况下直接读取；先用 `biopipe inspect --arg sep=...`。
- 坐标/数值精度由委托 Reader 决定。
