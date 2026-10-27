import type { Graph, InfoRule, PortContract } from "./types";

// Position, selection and memory-budget edits cannot change port compatibility.
export function contractSignature(graph: Graph): string {
  return JSON.stringify({ base_dir: graph.base_dir, edges: graph.edges,
    nodes: graph.nodes.map(({ id, kind, operator, params, source, input_count, route }) =>
      ({ id, kind, operator, params, source, input_count, route })) });
}
export function infoRuleLabel(rule: InfoRule): string {
  const type = rule.items ? `array<${Array.isArray(rule.items) ? rule.items.join(" | ") : rule.items}>` : Array.isArray(rule.type) ? rule.type.join(" | ") : rule.type || "待确认";
  const value = "const" in rule ? String(rule.const) : rule.enum?.join(" | ") ?? rule.display;
  return `${value ?? type}${rule.min !== undefined ? ` ≥ ${rule.min}` : ""}${rule.optional ? " · 可选" : ""}`;
}
export function contractRows(contract: PortContract | null): [string, string][] {
  if (!contract) return [["契约", "尚未声明，运行时检查数据结构"]];
  const rows: [string, string][] = [];
  if (contract.reader) rows.push(["reader", contract.reader]);
  if (contract.kind === "file") rows.push(["storage", "磁盘文件"]);
  else rows.push(["dims", contract.dims?.length ? contract.dims.join(" × ") : contract.ndim ? `${contract.ndim}D` : "由输入确定"]);
  for (const [key, rule] of Object.entries(contract.info || {})) rows.push([`info.${key}`, infoRuleLabel(rule)]);
  if (Array.isArray(contract.labels)) {
    for (const rule of contract.labels) {
      if (rule.optional && rule.values == null) continue;
      const values = Array.isArray(rule.values) ? rule.values : [rule.values];
      if (values.length) rows.push([`labels.${rule.dim}`, values.filter(Boolean).join(", ") || "待设置"]);
    }
  } else {
    for (const [dim, labels] of Object.entries(contract.labels || {}))
      rows.push([`labels.${dim}`, labels ? labels.slice(0, 8).join(", ") + (labels.length > 8 ? " …" : "") : "读取或运行后确定"]);
  }
  for (const field of contract.labels_any || []) rows.push(["labels · 任意维度", field || "待设置"]);
  for (const rule of contract.labels_axis || []) {
    const values = Array.isArray(rule.values) ? rule.values : [rule.values];
    rows.push([`labels · 第 ${rule.axis + 1} 维`, values.map(value => value || "待设置").join(", ")]);
  }
  for (const [dim, fields] of Object.entries(contract.axis_info || {})) rows.push([`axis_info.${dim}`, fields.join(", ")]);
  for (const rule of contract.parallel || []) rows.push([`axis_info${rule.dim ? `.${rule.dim}` : ""}`, (Array.isArray(rule.fields) ? rule.fields : [rule.fields]).join(", ") + (rule.allow_label ? " · 也接受同名列" : "")]);
  return rows;
}
