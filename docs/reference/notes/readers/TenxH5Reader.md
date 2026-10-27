## 审校补充（10x H5）

- Cell Ranger 3.0+ 的 `filtered_feature_bc_matrix.h5`/`raw_feature_bc_matrix.h5`。
- CSC 矩阵，feature × cell；`feature_type` 可分离 `Gene Expression` 与 `Antibody Capture`。
- 省略 `feature_type` 会保留所有 feature；CITE-seq 通常要分别读取。
- 重复 feature 名会加 `#position`；`feature_id_field` 可用 Ensembl/antibody id。
- `feature_types`/`genome` 在 `axis_info[feature]`；不要把它们当 data 列。
