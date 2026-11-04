import type { Catalog, Operator } from "./types";

// Stable category IDs are independent of localized labels and package ownership.
export const CANONICAL_CATEGORIES = ["quality_control", "statistics", "data", "machine_learning", "omics", "visualization"] as const;
const categoryNames: Record<string, string> = {
  quality_control: "质量控制", statistics: "统计分析", data: "数据整理",
  machine_learning: "机器学习", omics: "组学分析", visualization: "可视化", other: "未分类",
};
const categoryOrder = [...CANONICAL_CATEGORIES, "other"];
const categoryAliases: Record<string, string> = {
  analysis: "statistics", "statistical analysis": "statistics", survival: "statistics",
  plotting: "visualization", plots: "visualization", visualisation: "visualization",
  "quality control": "quality_control", qc: "quality_control",
  "data preparation": "data", "data processing": "data",
  "machine learning": "machine_learning", ml: "machine_learning",
  genetics: "omics", genome: "omics", genomics: "omics", transcriptomics: "omics", proteomics: "omics",
  "single cell": "omics", single_cell: "omics", microbiome: "omics", metagenomics: "omics",
  sequence: "omics", expression: "omics", "微生物组": "omics",
  plugins: "other", extensions: "other", "扩展算子": "other",
};

export function categoryId(category?: string | null): string {
  const name = category?.trim() ?? "";
  if (!name) return "other";
  const key = name.toLowerCase();
  if (Object.hasOwn(categoryNames, key)) return key;
  const localized = Object.entries(categoryNames).find(([, label]) => label === name);
  return localized?.[0] ?? (Object.hasOwn(categoryAliases, key) ? categoryAliases[key] : name);
}

export function categoryLabel(category?: string | null): string {
  const id = categoryId(category);
  return Object.hasOwn(categoryNames, id) ? categoryNames[id] : id;
}

export function compareCategories(a: string, b: string): number {
  const rank = (name: string) => {
    const index = categoryOrder.indexOf(categoryId(name));
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
