import manifest from "../../biopipe/builtin_packages.json";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { OperatorArtwork, OperatorPreview } from "./OperatorArtwork";
import {
  CANONICAL_CATEGORIES,
  categoryLabel,
  compareCategories,
  presentCatalog,
  presentOperator,
  presentReader,
} from "./operatorPresentation";
import type { Catalog, Operator, ReaderSpec } from "./types";

const operators = manifest.packages.flatMap(p =>
  p.descriptors.filter(d => d.kind === "operator")) as Operator[];
const readers = manifest.packages.flatMap(p =>
  p.descriptors.filter(d => d.kind === "reader")) as unknown as ReaderSpec[];
const catalog: Catalog = {schema_version: 1, operators, readers};

describe("operator and reader presentation", () => {
  it("groups every shipped operator and reader once, canonically", () => {
    const before = structuredClone(catalog);
    const presented = presentCatalog(catalog);
    const groups = [...new Set(presented.operators.map(o => o.category))].sort(compareCategories);
    expect(groups).toEqual([...CANONICAL_CATEGORIES]);
    expect(new Set(presented.operators.map(o => o.name)).size).toBe(operators.length);
    expect(presented.readers).toHaveLength(readers.length);
    expect(new Set(presented.readers!.map(r => r.name)).size).toBe(readers.length);
    expect(catalog).toEqual(before);
    for (const spec of presented.operators) {
      const original = operators.find(o => o.name === spec.name)!;
      expect(spec.contracts).toBe(original.contracts);
      expect(spec.parameters).toBe(original.parameters);
    }
  });

  it("gives every operator and reader a functional preview", () => {
    for (const spec of presentCatalog(catalog).operators) {
      expect(spec.title.trim(), spec.name).not.toBe("");
      expect(spec.description.trim(), spec.name).not.toBe("");
      expect(spec.category, spec.name).toBe(categoryLabel(spec.category));
    }
    for (const spec of presentCatalog(catalog).readers!) {
      expect(spec.title?.trim(), spec.name).not.toBe("");
      expect(spec.description?.trim(), spec.name).not.toBe("");
      expect(spec.extensions.length, spec.name).toBeGreaterThan(0);
      expect(spec.category, spec.name).toBe(categoryLabel(spec.category));
    }
  });

  it("marks readers that are unavailable on native Windows", () => {
    const windowsBlocked = readers.filter(r => (r.platforms?.length ?? 0) > 0);
    expect(windowsBlocked.map(r => r.name).sort()).toEqual(["BamReader", "BcfReader", "BigWigReader", "CramReader"]);
    const present = presentReader({...windowsBlocked[0], platforms: ["linux", "darwin"]});
    expect(present.platforms).toEqual(["linux", "darwin"]);
  });

  it("normalizes known aliases and keeps unknown plugin categories distinct", () => {
    expect(categoryLabel("Visualization")).toBe("Visualization");
    expect(categoryLabel(" visualization ")).toBe("Visualization");
    expect(categoryLabel("ANALYSIS")).toBe("Statistics");
    expect(categoryLabel("统计分析")).toBe("Statistics");
    expect(categoryLabel("Spatial biology")).toBe("Other");
    expect(categoryLabel("constructor")).toBe("Other");
    expect(categoryLabel("__proto__")).toBe("Other");
    const plugin = {...operators[0], name: "example.chart", category: "Visualization",
      preview: {kind: "boxplot", caption: "Custom plot"}};
    expect(presentOperator(plugin).preview).toBe(plugin.preview);
    expect(presentOperator(plugin).category).toBe("Visualization");
    expect(["Spatial biology", "Visualization", "Quality Control"].sort(compareCategories))
      .toEqual(["Visualization", "Quality Control", "Spatial biology"]);
  });

  it("uses category defaults for operators and leaves chart previews to declared plots", () => {
    const render = (category: string) => renderToStaticMarkup(<OperatorArtwork spec={{...operators[0],
      name: "example.new", category, icon: undefined, preview: undefined}}/>);
    expect(render("analysis")).toBe(render("Statistics"));
    expect(render("qc")).toBe(render("Quality Control"));
    expect(render("Spatial biology")).toBe(render("Other"));
    const plot = presentOperator({...operators[0], name: "example.plot", category: "Visualization",
      preview: {kind: "scatter", caption: "Plot"}});
    expect(renderToStaticMarkup(<OperatorPreview spec={plot}/>)).toContain("Plot");
    expect(renderToStaticMarkup(<OperatorPreview spec={presentOperator(operators[0])}/>)).toBe("");
  });

  it("renders declared icons and rejects unsupported image URLs", () => {
    const plugin = {...operators[0], name: "example.custom", category: "Statistics", preview: undefined};
    const renderIcon = (icon?: string | null) => renderToStaticMarkup(<OperatorArtwork spec={presentOperator({...plugin, icon})}/>);
    expect(renderIcon("Intersect")).not.toBe(renderIcon());
    expect(renderIcon("SquaresFour")).not.toBe(renderIcon());
    expect(renderIcon("UnknownFutureIcon")).toBe(renderIcon());
    expect(renderIcon("")).toBe(renderIcon());
    expect(renderIcon(null)).toBe(renderIcon());
    for (const name of ["constructor", "toString", "__proto__"]) {
      expect(renderIcon(name)).toBe(renderIcon());
    }

    const image = "data:image/svg+xml;base64,PHN2Zy8+";
    const spec = {...plugin, name: "example.picture", icon: "icons/custom.svg",
      icon_image: image, preview: {kind: "scatter", caption: "Plot"}};
    const art = renderToStaticMarkup(<OperatorArtwork spec={spec} size={18}/>);
    expect(art).toContain(`<img`);
    expect(art).toContain(`src="${image}"`);
    expect(art).toContain('width="18" height="18"');
    expect(art).not.toContain("data-glyph");
    expect(renderToStaticMarkup(<OperatorArtwork spec={spec} source/>)).not.toContain("<img");
    for (const url of ["https://example.com/icon.png", "file:///icons/icon.png", "data:text/html;base64,PHN2Zy8+"]) {
      const invalid = renderToStaticMarkup(<OperatorArtwork spec={{...spec, icon_image: url}}/>);
      const fallback = renderToStaticMarkup(<OperatorArtwork spec={{...spec, icon: undefined, icon_image: undefined, preview: undefined}}/>);
      expect(invalid).toBe(fallback);
    }
  });
});
