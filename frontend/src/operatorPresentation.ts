import type { Catalog, Operator } from "./types";

const categoryOrder = ["质量控制", "统计分析", "数据整理", "可视化", "未分类"];
const categoryAliases: Record<string, string> = {
  analysis: "统计分析", statistics: "统计分析", "statistical analysis": "统计分析",
  visualization: "可视化", plotting: "可视化", plots: "可视化",
  "quality control": "质量控制", quality_control: "质量控制", qc: "质量控制",
  data: "数据整理", "data preparation": "数据整理", "data processing": "数据整理",
  plugins: "未分类", extensions: "未分类", "扩展算子": "未分类", microbiome: "微生物组",
};

export function categoryLabel(category?: string | null): string {
  const name = category?.trim() ?? "";
  const key = name.toLowerCase();
  return Object.hasOwn(categoryAliases, key) ? categoryAliases[key] : (name || "未分类");
}

export function compareCategories(a: string, b: string): number {
  const rank = (name: string) => {
    const index = categoryOrder.indexOf(name);
    return index < 0 ? categoryOrder.length : index;
  };
  return rank(a) - rank(b) || a.localeCompare(b, "zh-CN");
}

export function presentOperator(spec: Operator): Operator {
  return {
    ...spec,
    category: categoryLabel(spec.category),
  };
}

export function presentCatalog(catalog: Catalog): Catalog {
  return { ...catalog, operators: catalog.operators.map(presentOperator) };
}
