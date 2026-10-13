import manifest from "../../biopipe/builtin_packages.json";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OperatorArtwork, OperatorPreview } from "./OperatorArtwork";
import { builtinPresentation, categoryLabel, compareCategories, presentCatalog, presentOperator } from "./operatorPresentation";
import type { Catalog, Operator } from "./types";

// Exercise the shipped registry, including descriptors already present in saved
// provider generations, instead of duplicating synthetic operator metadata.
const operators = manifest.packages.flatMap(p =>
  p.descriptors.filter(d => d.kind === "operator")) as Operator[];
const catalog: Catalog = {schema_version: 1, operators};

describe("operator presentation", () => {
  it("groups every shipped operator once, with no duplicate language categories", () => {
    const before = structuredClone(catalog);
    const presented = presentCatalog(catalog);
    const groups = [...new Set(presented.operators.map(o => o.category))].sort(compareCategories);
    expect(groups).toEqual(["质量控制", "统计分析", "数据整理", "可视化"]);
    expect(new Set(presented.operators.map(o => o.name)).size).toBe(operators.length);
    expect(catalog).toEqual(before);
    for (const spec of presented.operators) {
      const original = operators.find(o => o.name === spec.name)!;
      expect(spec.contracts).toBe(original.contracts);
      expect(spec.parameters).toBe(original.parameters);
    }
  });

  it.each(Object.keys(builtinPresentation))("renders %s artwork in nodes/library and inspector", name => {
    const spec = presentOperator(operators.find(o => o.name === name)!);
    const art = renderToStaticMarkup(<OperatorArtwork spec={spec}/>);
    expect(spec.preview?.kind).toBeTruthy();
    expect(art).toContain(`data-glyph="${spec.preview!.kind}"`);
    expect(art).toContain('aria-hidden="true"');
    expect(renderToStaticMarkup(<OperatorPreview spec={spec}/>)).toContain(spec.preview!.caption);
  });

  it("does not silently render any shipped operator as a generic placeholder", () => {
    for (const spec of presentCatalog(catalog).operators) {
      const generic = renderToStaticMarkup(<OperatorArtwork spec={{...spec, icon: undefined, preview: undefined}}/>);
      expect(renderToStaticMarkup(<OperatorArtwork spec={spec}/>), spec.name).not.toBe(generic);
    }
  });

  it("also merges plugin category aliases and preserves plugin-provided visuals", () => {
    expect(categoryLabel(" Visualization ")).toBe("可视化");
    expect(categoryLabel("ANALYSIS")).toBe("统计分析");
    const plugin = {...operators[0], name: "example.chart", category: "Visualization",
      preview: {kind: "boxplot", caption: "Custom plot"}};
    expect(presentOperator(plugin).preview).toBe(plugin.preview);
    expect(presentOperator(plugin).category).toBe("可视化");
    expect(categoryLabel("Spatial biology")).toBe("Spatial biology");
    expect(["Spatial biology", "可视化", "质量控制"].sort(compareCategories))
      .toEqual(["质量控制", "可视化", "Spatial biology"]);
  });
});
