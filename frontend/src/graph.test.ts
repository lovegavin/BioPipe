import { describe, expect, it } from "vitest";
import {
  autoLayout,
  executionOrder,
  makeNode,
  normalizeGraph,
  runSignature,
  wouldCycle,
} from "./graph";
import { spillCounts } from "./Results";
import type { Graph, Operator, RunEvent } from "./types";
const graph: Graph = {
  schema_version: 2,
  name: "branch",
  base_dir: ".",
  memory: { enabled: true },
  nodes: ["source", "qc", "pca", "summary", "join"].map((id, i) => ({
    id,
    kind: i ? "operator" : "source",
    title: id,
    position: { x: 0, y: 0 },
    params: {},
    input_count: id === "join" ? 2 : 1,
  })),
  edges: [
    ["source", "qc", "in-0"],
    ["qc", "pca", "in-0"],
    ["qc", "summary", "in-0"],
    ["pca", "join", "in-0"],
    ["qc", "join", "in-1"],
  ].map(([source, target, targetHandle]) => ({
    id: `${source}-${target}`,
    source,
    target,
    targetHandle,
    sourceHandle: "out",
  })),
};
describe("visual DAG contract", () => {
  it("matches backend null defaults and ignores visual-only edits in run identity", () => {
    const backend = structuredClone(graph);
    backend.nodes = backend.nodes.map((n) => ({
      ...n,
      operator: n.operator ?? null,
      source: n.source ?? null,
    }));
    expect(runSignature(backend)).toBe(runSignature(graph));
    backend.nodes[0].title = "renamed";
    backend.nodes[0].position.x = 99;
    expect(runSignature(backend)).toBe(runSignature(graph));
    backend.nodes[1].params = { threshold: 0.3 };
    expect(runSignature(backend)).not.toBe(runSignature(graph));
  });
  it("keeps run identity across API field reordering but detects changed inputs", () => {
    const client = structuredClone(graph);
    client.nodes[1].params = {
      dim: "feature",
      threshold: 0.05,
      output: "clean",
    };
    const response = structuredClone(client);
    // Pydantic emits sourceHandle before targetHandle; the demo stores the reverse.
    response.edges = response.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
    }));
    response.nodes[1].params = {
      output: "clean",
      threshold: 0.05,
      dim: "feature",
    };
    expect(runSignature(response)).toBe(runSignature(client));
    response.edges[3].targetHandle = "in-1";
    expect(runSignature(response)).not.toBe(runSignature(client));
  });
  it("keeps a deterministic order across independent branches and layout changes", () => {
    expect(executionOrder(graph)).toEqual([
      "source",
      "qc",
      "pca",
      "summary",
      "join",
    ]);
    const placed = autoLayout(graph);
    expect(executionOrder(placed)).toEqual(executionOrder(graph));
    expect(placed.nodes[2].position.x).toEqual(placed.nodes[3].position.x);
    expect(placed.nodes[2].position.y).not.toEqual(placed.nodes[3].position.y);
    expect(placed.edges[4].targetHandle).toBe("in-1");
    expect(graph.nodes[0].position).toEqual({ x: 0, y: 0 });
  });
  it("rejects a return edge but permits reuse and independent side branches", () => {
    expect(wouldCycle(graph.edges, "join", "qc")).toBe(true);
    expect(wouldCycle(graph.edges, "qc", "join")).toBe(false);
    expect(wouldCycle(graph.edges, "pca", "pca")).toBe(true);
    const cyclic = {
      ...graph,
      edges: [
        ...graph.edges,
        {
          id: "bad",
          source: "join",
          target: "qc",
          sourceHandle: "out",
          targetHandle: "in-0",
        },
      ],
    };
    expect(() => executionOrder(cyclic)).toThrow();
  });
  it("creates unique outputs and restores omitted view defaults", () => {
    const spec = {
      id: "qc",
      title: "QC",
      inputs_arity: "*",
      output_parameter: "output",
      parameters: [{ key: "labels", type: "list", default: ["x"] }],
    } as Operator;
    const first = makeNode(graph, spec, { x: 3, y: 4 });
    const second = makeNode(
      { ...graph, nodes: [...graph.nodes, first] },
      spec,
      { x: 3, y: 4 },
    );
    expect(second.id).not.toBe(first.id);
    expect(first.input_count).toBe(2);
    expect(second.params.output).not.toBe(first.params.output);
    expect(normalizeGraph(graph).memory.auto_spill).toBe(true);
    expect(() =>
      normalizeGraph({ ...graph, schema_version: 99 } as unknown as Graph),
    ).toThrow();
  });
  it("separates planned storage, emergency spill, corrections and final saves", () => {
    const events = [
      "full_step_admission",
      "rss_pressure",
      "actual_output_size",
      "final_output",
    ].map((reason) => ({ event: "spill", time: "x", reason }) as RunEvent);
    events.push({
      event: "emergency_spill",
      time: "x",
      reason: "rss_pressure",
    });
    expect(spillCounts(events)).toEqual({
      planned: 1,
      emergency: 1,
      correction: 1,
      final: 1,
    });
  });
});

it('preserves imported global configuration and the disabled memory flag', () => {
  const imported = {...graph, memory:{enabled:false}, params:{seed:42}, runtime:{custom:true}, manifest_extra:{notes:'lab'}};
  const restored = normalizeGraph(imported);
  expect(restored.memory.enabled).toBe(false);
  expect(restored.params).toEqual({seed:42});
  expect(restored.runtime).toEqual({custom:true});
  expect(restored.manifest_extra).toEqual({notes:'lab'});
  expect(runSignature(restored)).not.toBe(runSignature({...restored,params:{seed:43}}));
});
