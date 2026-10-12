export type PanelSide = "library" | "inspector";
export type PanelWidths = Record<PanelSide, number | null>;
export const automaticPanels: PanelWidths = { library: null, inspector: null };
export const panelLimits = { library: { min: 200, max: 360 }, inspector: { min: 256, max: 420 } };
const clamp = (n: number, min: number, max: number) => Math.round(Math.max(min, Math.min(max, n)));

// Remember the user's preferred widths; only constrain their displayed size when
// the window shrinks, so returning to a large window restores the preference.
export function resolvePanels(preferred: PanelWidths, windowWidth: number) {
  const extra = Math.max(0, windowWidth - 1440);
  let library = clamp(preferred.library ?? (windowWidth <= 760 ? 224 : windowWidth <= 1180 ? 200 : 208 + extra * .08), 200, 360);
  let inspector = clamp(preferred.inspector ?? 272 + extra * .1, 256, 420);
  const available = windowWidth - 64 - 480;
  if (windowWidth > 1180 && library + inspector > available) {
    const scale = (available - 456) / (library + inspector - 456);
    library = Math.floor(200 + (library - 200) * scale);
    inspector = Math.floor(256 + (inspector - 256) * scale);
  }
  return { library, inspector };
}

export function panelMaximum(side: PanelSide, widths: Record<PanelSide, number>, windowWidth: number) {
  const { min, max } = panelLimits[side];
  return windowWidth <= 1180 ? max : clamp(windowWidth - 64 - 480 - widths[side === "library" ? "inspector" : "library"], min, max);
}
