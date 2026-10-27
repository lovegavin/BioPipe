import {
  ArrowsDownUp,
  ArrowsIn,
  ChartBar,
  ChartLine,
  ChartScatter,
  CheckSquare,
  CirclesThree,
  Columns,
  Database,
  Dna,
  Funnel,
  Intersect,
  ListBullets,
  MinusSquare,
  Scales,
  Selection,
  Shuffle,
  SortAscending,
  Ruler,
  Tag,
  TextT,
  TrendUp,
  TreeStructure,
  Unite,
  SquaresFour,
  GridNine,
  Stack,
  SlidersHorizontal,
  Function,
  PuzzlePiece,
  Sigma,
} from "@phosphor-icons/react";
import type { IconProps } from "@phosphor-icons/react";
import type { ComponentType } from "react";
import { categoryLabel } from "./operatorPresentation";
const icons: Record<string, ComponentType<IconProps>> = {
  ArrowsDownUp,
  ArrowsIn,
  ChartBar,
  ChartLine,
  ChartScatter,
  CheckSquare,
  CirclesThree,
  Columns,
  Database,
  Dna,
  Funnel,
  Intersect,
  ListBullets,
  MinusSquare,
  Scales,
  Selection,
  Shuffle,
  SortAscending,
  Ruler,
  Tag,
  TextT,
  TrendUp,
  TreeStructure,
  Unite,
  Stack,
  SlidersHorizontal,
  Function,
  PuzzlePiece,
  Sigma,
  SquaresFour,
  GridNine,
};
export function OperatorIcon({
  name,
  category,
  ...props
}: IconProps & { name?: string; category?: string }) {
  const defaults: Record<string, ComponentType<IconProps>> = {
    "统计分析": Sigma, "质量控制": CheckSquare, "数据整理": SlidersHorizontal,
    "可视化": ChartBar, "微生物组": CirclesThree,
  };
  const label = categoryLabel(category);
  const fallback = Object.hasOwn(defaults, label) ? defaults[label] : SquaresFour;
  const Icon = name && Object.hasOwn(icons, name) ? icons[name] : fallback;
  return <Icon {...props} />;
}
