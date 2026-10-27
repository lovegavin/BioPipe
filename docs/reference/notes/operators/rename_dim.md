## 审校补充（重命名维度）

- 只改维度名，不改 data/labels 的值；`from` 必须存在，`to` 不能与现有维度重名。
- 用于把通用 `feature/sample` 改成领域名（gene/cell、protein/sample），便于后续算子匹配。
- 不代表数据语义变化；如果值含义也变了，需要同时 `transpose`/转换算子。
- 下游 `dims`/labels 参数要用新名字；旧名字会报错。
