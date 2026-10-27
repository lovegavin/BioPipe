## 审校补充（PLINK 2.x）

- 只有 `.pgen` + `.pvar` + `.psam` 同时存在时才由 Plink2Reader 认领。
- 输出 variant × sample 的硬调用；多等位按 ALT 拆分。
- `.pvar` 支持 VCF-style 或 BIM-style header；坐标/ID 解析随 header 变化。
- 三个文件不能压缩；Reader 需要 sibling 留在原目录。
- 与 PLINK1 的标签/缺失语义保持一致，但文件格式不同，不要混用。
