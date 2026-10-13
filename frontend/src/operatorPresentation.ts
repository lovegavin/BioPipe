import type { Catalog, Operator } from "./types";

const categoryOrder = ["质量控制", "统计分析", "数据整理", "可视化", "扩展算子"];
const categoryAliases: Record<string, string> = {
  analysis: "统计分析", statistics: "统计分析", "statistical analysis": "统计分析",
  visualization: "可视化", plotting: "可视化", plots: "可视化",
  "quality control": "质量控制", quality_control: "质量控制", qc: "质量控制",
  data: "数据整理", "data preparation": "数据整理", "data processing": "数据整理",
  plugins: "扩展算子", extensions: "扩展算子", microbiome: "微生物组",
};

export function categoryLabel(category: string): string {
  const name = category.trim();
  return categoryAliases[name.toLowerCase()] ?? (name || "扩展算子");
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
  bin: artwork("数据整理", "ChartBar", "binning", "连续值分箱"),
  filter_by: artwork("数据整理", "Funnel", "filter", "按指标筛选"),
  rank_axis: artwork("数据整理", "ListBullets", "ranking", "特征排序与选择"),
  join: artwork("数据整理", "Unite", "join", "按共有标签关联"),
  aggregate: artwork("数据整理", "Stack", "aggregate", "按组汇总"),
  cluster_axis: artwork("统计分析", "Intersect", "clustering", "相似样本聚类"),
  reduce_axis: artwork("统计分析", "Sigma", "axis_summary", "沿维度汇总统计"),
  reduce: artwork("统计分析", "ChartScatter", "embedding", "高维数据投影"),
  diversity: artwork("统计分析", "ChartBar", "diversity", "丰富度与均匀度"),
  distance_matrix: artwork("统计分析", "SquaresFour", "distance", "样本间距离"),
  correlation: artwork("统计分析", "Intersect", "correlation", "变量间相关性"),
  permanova: artwork("统计分析", "Sigma", "permutation", "组间差异与置换分布"),
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
