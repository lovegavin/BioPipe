import type { Catalog, Operator } from "./types";

const categoryOrder = ["质量控制", "统计分析", "数据整理", "可视化", "未分类"];
const categoryAliases: Record<string, string> = {
  analysis: "统计分析", statistics: "统计分析", "statistical analysis": "统计分析",
  visualization: "可视化", plotting: "可视化", plots: "可视化",
  "quality control": "质量控制", quality_control: "质量控制", qc: "质量控制",
  "single cell": "质量控制", single_cell: "质量控制", proteomics: "数据整理",
  data: "数据整理", "data preparation": "数据整理", "data processing": "数据整理",
  plugins: "未分类", extensions: "未分类", "扩展算子": "未分类", microbiome: "微生物组",
  genetics: "统计分析",
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

// Presentation is independent of package ownership and runtime fingerprints.
// Saved catalogs and already-installed providers receive the same UI treatment.
const artwork = (category: string, icon: string, kind: string, caption: string) => ({
  category, icon, preview: { kind, caption },
});
export const builtinPresentation = {
  bin: { category: "数据整理", icon: "Columns" },
  filter_by: { category: "数据整理", icon: "Funnel" },
  rank_axis: { category: "数据整理", icon: "SortAscending" },
  join: { category: "数据整理", icon: "Unite" },
  aggregate: { category: "数据整理", icon: "Stack" },
  cluster_axis: { category: "统计分析", icon: "TreeStructure" },
  combat: { category: "数据整理", icon: "ArrowsDownUp" },
  reduce_axis: { category: "统计分析", icon: "Sigma" },
  reduce: { category: "统计分析", icon: "ArrowsIn" },
  diversity: { category: "统计分析", icon: "CirclesThree" },
  distance_matrix: { category: "统计分析", icon: "Ruler" },
  correlation: { category: "统计分析", icon: "Intersect" },
  permanova: { category: "统计分析", icon: "Shuffle" },
  doublet_detect: { category: "质量控制", icon: "CheckSquare" },
  marker_score: { category: "统计分析", icon: "Tag" },
  pseudobulk: { category: "统计分析", icon: "Stack" },
  gsea: { category: "统计分析", icon: "TrendUp" },
  ora: { category: "统计分析", icon: "Selection" },
  limma_de: { category: "统计分析", icon: "ArrowsDownUp" },
  meta_analysis: { category: "统计分析", icon: "Scales" },
  prs: { category: "统计分析", icon: "Dna" },
  ancom_bc: { category: "统计分析", icon: "CirclesThree" },
  aldex2: { category: "统计分析", icon: "CirclesThree" },
  protein_rollup: { category: "数据整理", icon: "Stack" },
  ssgsea: { category: "统计分析", icon: "TrendUp" },
  spectral_embedding: { category: "统计分析", icon: "CirclesThree" },
  locally_linear_embedding: { category: "统计分析", icon: "TreeStructure" },
  gaussian_random_projection: { category: "数据整理", icon: "Shuffle" },
  topic_lda: { category: "统计分析", icon: "ListBullets" },
  wilcoxon: { category: "统计分析", icon: "Scales" },
  friedman: { category: "统计分析", icon: "TrendUp" },
  bartlett: { category: "统计分析", icon: "ChartBar" },
  normaltest: { category: "统计分析", icon: "Sigma" },
  bonferroni: { category: "统计分析", icon: "Selection" },
  fisher_combined: { category: "统计分析", icon: "Function" },
  dotplot: artwork("可视化", "ChartScatter", "dotplot", "点大小与强度"),
  violin: artwork("可视化", "ChartLine", "violin", "分组密度与分布"),
  barplot: artwork("可视化", "ChartBar", "composition", "各组组成比例"),
} satisfies Record<string, Pick<Operator, "category" | "icon" | "preview">>;

export function presentOperator(spec: Operator): Operator {
  const fallback = (builtinPresentation as Record<string, Partial<Operator>>)[spec.name];
  return {
    ...spec,
    category: categoryLabel(fallback?.category ?? spec.category),
    icon: spec.icon ?? fallback?.icon,
    preview: spec.preview ?? fallback?.preview,
  };
}

export function presentCatalog(catalog: Catalog): Catalog {
  return { ...catalog, operators: catalog.operators.map(presentOperator) };
}
