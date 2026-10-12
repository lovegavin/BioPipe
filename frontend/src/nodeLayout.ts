// Shared by the node renderer and React Flow so ports and edges stay aligned.
export const NODE_LAYOUT = {
  width: 232,
  bodyHeight: 72,
  portMinHeight: 28,
  portGap: 18,
  portPadding: 10,
} as const;

export const portRowHeight = (count: number) =>
  Math.max(
    NODE_LAYOUT.portMinHeight,
    count * NODE_LAYOUT.portGap + NODE_LAYOUT.portPadding,
  );

export const portOffset = (count: number, index: number) =>
  (portRowHeight(count) - (count - 1) * NODE_LAYOUT.portGap) / 2 +
  index * NODE_LAYOUT.portGap;
