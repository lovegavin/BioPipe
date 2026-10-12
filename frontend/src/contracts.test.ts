import { describe, expect, it } from "vitest";
import { contractRows, contractSignature, infoRuleLabel } from "./contracts";
import type { Graph } from "./types";

describe("port info", () => {
  it("shows semantics separately from the tensor container and annotation binding", () => {
    expect(contractRows({ dims: ["variant", "sample"], info: { representation: { const: "hard_call" }, ploidy: { const: 2 } }, axis_info: { variant: ["chrom", "pos"] } }))
      .toEqual([["dims", "variant × sample"], ["info.representation", "hard_call"], ["info.ploidy", "2"], ["axis_info.variant", "chrom, pos"]]);
  });
  it("does not present unknown file labels as guaranteed fields", () => {
    expect(contractRows({ labels: { statistic: null } })).toContainEqual(["labels.statistic", "读取或运行后确定"]);
    expect(infoRuleLabel({ type: "object", optional: true })).toBe("object · 可选");
  });
  it("renders parameter-dependent required fields and ignores unset optional color", () => {
    const rows = contractRows({ labels: [{ dim: "statistic", values: "P" }, { dim: "statistic", values: null, optional: true }] });
    expect(rows.filter(([key]) => key.startsWith("labels"))).toEqual([["labels.statistic", "P"]]);
  });
  it("refreshes contracts on parameter changes without refetching for node movement or budget edits", () => {
    const graph = { schema_version: 1, name: "test", base_dir: ".", memory: { enabled: true }, edges: [], nodes: [{ id: "pca", kind: "operator", operator: "pca", title: "PCA", position: { x: 0, y: 0 }, params: { dim: "feature" }, input_count: 1 }] } as Graph;
    const moved = structuredClone(graph);
    moved.nodes[0].position.x = 100;
    moved.memory.budget_mb = 128;
    expect(contractSignature(moved)).toBe(contractSignature(graph));
    moved.nodes[0].params.dim = "variant";
    expect(contractSignature(moved)).not.toBe(contractSignature(graph));
  });
  it("shows clinical column requirements even when the dimension name is user-defined", () => {
    expect(contractRows({ labels_axis: [{axis: 1, values: ["time", "event", null]}], labels_any: ["group"] }))
      .toEqual([["dims", "由输入确定"], ["labels · 任意维度", "group"], ["labels · 第 2 维", "time, event, 待设置"]]);
  });
});
