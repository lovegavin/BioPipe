import {
  ArrowsDownUp,
  ChartBar,
  ChartLine,
  ChartScatter,
  CheckSquare,
  Database,
  Dna,
  Funnel,
  Intersect,
  ListBullets,
  MinusSquare,
  Scales,
  Selection,
  Tag,
  TextT,
  TrendUp,
  Unite,
  SquaresFour,
  Stack,
  SlidersHorizontal,
  Function,
  PuzzlePiece,
  Sigma,
} from "@phosphor-icons/react";
import type { IconProps } from "@phosphor-icons/react";
import type { ComponentType } from "react";
const icons: Record<string, ComponentType<IconProps>> = {
  ArrowsDownUp,
  ChartBar,
  ChartLine,
  ChartScatter,
  CheckSquare,
  Database,
  Dna,
  Funnel,
  Intersect,
  ListBullets,
  MinusSquare,
  Scales,
  Selection,
  Tag,
  TextT,
  TrendUp,
  Unite,
  Stack,
  SlidersHorizontal,
  Function,
  PuzzlePiece,
  Sigma,
};
export function OperatorIcon({
  name,
  ...props
}: IconProps & { name?: string }) {
  const Icon = icons[name || ""] || SquaresFour;
  return <Icon {...props} />;
}
