import type { Catalog, Graph, GraphEdge, GraphNode, Operator, RouteDefinition } from "./types";

export const clone = <T>(value: T): T => structuredClone(value);
export function runSignature(graph: Graph): string {
  const execution = {
    base_dir: graph.base_dir,
    memory: graph.memory,
    params: graph.params || {},
    runtime: graph.runtime || {},
    manifest_extra: graph.manifest_extra || {},
    plugin_lock: graph.plugin_lock || {},
    edges: graph.edges,
    nodes: graph.nodes.map(
      ({ id, kind, operator, params, source, input_count, route, context_params }) => ({
        id,
        kind,
        operator: operator ?? null,
        params,
        context_params: context_params || {},
        source: source ?? null,
        input_count,
        route: route ? { id: route.id, version: route.version, interface: route.graph.interface, execution: runSignature(route.graph) } : null,
      }),
    ),
  };
  // JSON object field order carries no meaning; array order preserves execution ties.
  return JSON.stringify(execution, (_key, value) =>
    value !== null && typeof value === "object" && !Array.isArray(value)
      ? Object.fromEntries(
          Object.keys(value)
            .sort()
            .map((key) => [key, value[key]]),
        )
      : value,
  );
}
export function normalizeGraph(value: Graph): Graph {
  if (
    ![1, 2].includes(value.schema_version) ||
    !Array.isArray(value.nodes) ||
    !Array.isArray(value.edges)
  )
    throw new Error("需要 BioPipe Studio 工作流 JSON。");
  return {
    schema_version: value.schema_version,
    interface: value.interface,
    plugin_lock: value.plugin_lock || {},
    params: value.params || {},
    runtime: value.runtime || {},
    manifest_extra: value.manifest_extra || {},
    name: value.name || "我的工作流",
    base_dir: value.base_dir || ".",
    memory: {
      ...value.memory,
      enabled: value.memory?.enabled ?? true,
      auto_spill: value.memory?.auto_spill ?? true,
    },
    nodes: value.nodes.map((node) => ({
      ...node,
      title: node.title || node.operator || "输入数据",
      params: node.params || {},
      input_count: node.input_count ?? 1,
    })),
    edges: value.edges.map((edge) => ({
      ...edge,
      targetHandle: edge.targetHandle || "in-0",
      sourceHandle: edge.sourceHandle || "out",
    })),
  };
}
export function wouldCycle(
  edges: GraphEdge[],
  source: string,
  target: string,
): boolean {
  const seen = new Set<string>(),
    queue = [target];
  while (queue.length) {
    const id = queue.pop()!;
    if (id === source) return true;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const edge of edges) if (edge.source === id) queue.push(edge.target);
  }
  return false;
}
// Creation order breaks ties, matching the Python compiler's fixed sequence.
export function executionOrder(graph: Graph): string[] {
  const indegree = new Map(graph.nodes.map((node) => [node.id, 0]));
  for (const edge of graph.edges)
    indegree.set(edge.target, (indegree.get(edge.target) || 0) + 1);
  const order: string[] = [],
    seen = new Set<string>();
  while (order.length < graph.nodes.length) {
    const node = graph.nodes.find(
      (node) => !seen.has(node.id) && indegree.get(node.id) === 0,
    );
    if (!node) throw new Error("工作流中存在环路或失效连线。");
    seen.add(node.id);
    order.push(node.id);
    for (const edge of graph.edges)
      if (edge.source === node.id)
        indegree.set(edge.target, indegree.get(edge.target)! - 1);
  }
  return order;
}
export function autoLayout(graph: Graph): Graph {
  const next = clone(graph),
    depths = new Map<string, number>(),
    levels = new Map<number, string[]>();
  for (const id of executionOrder(graph)) {
    const parents = graph.edges.filter((edge) => edge.target === id);
    const depth = parents.length
      ? Math.max(...parents.map((edge) => depths.get(edge.source) || 0)) + 1
      : 0;
    depths.set(id, depth);
    levels.set(depth, [...(levels.get(depth) || []), id]);
  }
  const maxRows = Math.max(
    1,
    ...[...levels.values()].map((level) => level.length),
  );
  for (const node of next.nodes) {
    const depth = depths.get(node.id) || 0,
      level = levels.get(depth)!;
    node.position = {
      x: 60 + depth * 280,
      y: 60 + (maxRows - level.length) * 100 + level.indexOf(node.id) * 200,
    };
  }
  return next;
}
export function makeNode(
  graph: Graph,
  spec: Operator | undefined,
  position: { x: number; y: number },
): GraphNode {
  const prefix = spec?.name || "data";
  let number = 1;
  const names = new Set(
    graph.nodes.flatMap((n) => [n.id, String(n.params.output || "")]),
  );
  let id = `${prefix}_${number}`;
  while (names.has(id) || names.has(`${id}_out`)) id = `${prefix}_${++number}`;
  return {
    id,
    kind: spec ? "operator" : "source",
    operator: spec?.name,
    title: spec?.title || "输入数据",
    position,
    input_count: spec?.inputs_arity === "*" ? 2 : (spec?.inputs_arity ?? 0),
    params: spec
      ? {
          ...Object.fromEntries(
            spec.parameters
              .filter((p) => p.default !== undefined)
              .map((p) => [p.key, clone(p.default)]),
          ),
          ...(spec.output_parameter ? { output: `${id}_out` } : {}),
        }
      : {},
    ...(spec
      ? {}
      : {
          source: {
            path: "",
            dims: ["sample", "feature"],
            labels: { sample: "auto", feature: "builtin" },
            args: {},
          },
        }),
  };
}
export function specFor(
  node: GraphNode,
  catalog: Catalog,
): Operator | undefined {
  if (node.kind === "route" && node.route) return routeSpec(node.route);
  return catalog.operators.find((o) => o.name === node.operator);
}
export function routeSpec(route: RouteDefinition): Operator {
  return { name: route.id, title: route.name, category: "路线算子", description: `${route.graph.nodes.filter(n => n.kind !== "source").length} 个内部节点 · v${route.version}`,
    icon: "Stack", inputs_arity: route.graph.interface?.inputs.length || 0,
    outputs: route.graph.interface?.outputs.map(p => p.label) || [], output_parameter: null,
    input_type: "info", output_type: "info", memory_modes: ["adaptive"], supports_cuda: false, parameters: [] };
}
export function makeRouteNode(graph: Graph, route: RouteDefinition, position: {x: number; y: number}): GraphNode {
  const node = makeNode(graph, routeSpec(route), position);
  return { ...node, kind: "route", route: clone(route) };
}
export function retainedOutputs(node: GraphNode, spec?: Operator): string[] {
  return node.kind === "source" ? [node.id] : node.kind === "route"
    ? Array.from({length: outputCount(node, spec)}, (_, i) => `${node.id}__out_${i + 1}`)
    : spec?.output_parameter ? [String(node.params.output || node.id)] : spec?.outputs || [];
}
export function displayTitle(node: GraphNode, spec?: Operator): string {
  if (
    node.kind === "source" ||
    !spec ||
    (node.title !== spec.title &&
      node.title !== spec.name &&
      !spec.title_aliases?.includes(node.title))
  )
    return node.title;
  if (spec.title_parameter) {
    const { key, values } = spec.title_parameter;
    // Imported workflows may omit a parameter and use the operator's runtime default.
    const value = node.params[key] ?? spec.runtime_defaults?.[key];
    return values[String(value)] ?? spec.title;
  }
  return spec.title;
}
export function inputCount(node: GraphNode, spec?: Operator): number {
  return node.kind === "source"
    ? 0
    : spec?.inputs_arity === "*"
      ? node.input_count
      : Number(spec?.inputs_arity ?? 1);
}
export function outputCount(node: GraphNode, spec?: Operator): number {
  return node.kind === "source" || spec?.output_parameter
    ? 1
    : spec?.outputs.length || 0;
}
export function bytes(value?: number): string {
  if (value === undefined || value === null) return "—";
  if (value < 1024) return `${value} B`;
  const unit = value < 1024 ** 2 ? "KiB" : value < 1024 ** 3 ? "MiB" : "GiB";
  const scale = unit === "KiB" ? 1024 : unit === "MiB" ? 1024 ** 2 : 1024 ** 3;
  return `${(value / scale).toFixed(value / scale < 10 ? 2 : 1)} ${unit}`;
}
