import { describe, expect, it } from "vitest";
import { automaticPanels, resolvePanels, panelMaximum } from "./panelLayout";

describe("side panel layout", () => {
  it("keeps desktop defaults and gives large windows more room", () => {
    expect(resolvePanels(automaticPanels, 1440)).toEqual({ library: 208, inspector: 272 });
    expect(resolvePanels(automaticPanels, 2048)).toEqual({ library: 257, inspector: 333 });
    expect(resolvePanels(automaticPanels, 1000).library).toBe(200);
  });
  it("keeps 480px of clear canvas when both panels are wide", () => {
    const preference = { library: 360, inspector: 420 };
    for (const viewport of [1181, 1200, 1366, 1440, 2048]) {
      const actual = resolvePanels(preference, viewport);
      expect(viewport - 64 - actual.library - actual.inspector).toBeGreaterThanOrEqual(480);
      expect(actual.library).toBeGreaterThanOrEqual(200);
      expect(actual.inspector).toBeGreaterThanOrEqual(256);
    }
    expect(resolvePanels(preference, 2048)).toEqual(preference);
  });
  it("constrains one panel against the other without changing stored preferences", () => {
    const widths = { library: 360, inspector: 350 };
    expect(panelMaximum("inspector", widths, 1200)).toBe(296);
    expect(panelMaximum("library", widths, 1200)).toBe(306);
    expect(panelMaximum("inspector", widths, 960)).toBe(420); // drawer overlays the canvas
    expect(widths).toEqual({ library: 360, inspector: 350 });
  });
});
