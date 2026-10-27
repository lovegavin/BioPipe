import type { Graph, GraphNode, GraphEdge, TargetRef } from "./types";
import { clone } from "./graph";
import {defaultTarget, executionConfig, withExecution} from './execution';

const FORMAT = "biopipe/graph-fragment-v1";
export type Fragment = { format: typeof FORMAT; base_dir?: string; nodes: GraphNode[]; edges: GraphEdge[];
  node_targets?: Record<string, TargetRef>; file_locations?: Record<string, TargetRef> };
export function copyFragment(graph: Graph, selected: string[]): Fragment {
  const ids = new Set(selected);
  const config = executionConfig(graph);
  return clone({ format: FORMAT, base_dir: graph.base_dir, nodes: graph.nodes.filter(n => ids.has(n.id)).map(node => node.source
      ? {...node, source: {...node.source, location: node.source.location ?? defaultTarget(graph)}} : node),
    edges: graph.edges.filter(e => ids.has(e.source) && ids.has(e.target)),
    node_targets: Object.fromEntries(Object.entries(config.node_targets || {}).filter(([id]) => ids.has(id))),
    file_locations: Object.fromEntries(Object.entries(config.file_locations || {}).filter(([key]) => selected.some(id => key.startsWith(`${id}.params.`) || key.startsWith(`${id}.source.args.`)))) });
}
export function parseFragment(text: string): Fragment {
  const value = JSON.parse(text) as Fragment;
  if (value.format !== FORMAT || !Array.isArray(value.nodes) || !Array.isArray(value.edges) ||
      value.nodes.length > 1000 || value.edges.length > 5000 || !value.nodes.every(n => n.id && n.position && ["source", "operator", "route"].includes(n.kind)))
    throw Error("剪贴板中没有 BioPipe 节点。");
  return value;
}
function rebaseSource(path: string, from: string, to: string): string {
  const absolute = (value: string) => /^(?:[A-Za-z]:[\\/]|[\\/])/.test(value);
  if (!path || from === to || absolute(path)) return path;
  if (absolute(from) || absolute(to))
    throw Error("跨目录粘贴数据节点时，请先将两张画布的基础目录设为项目内相对路径。");
  const parts = (value: string) => value.replaceAll("\\", "/").split("/").reduce<string[]>((items, part) => {
    if (part === ".." && items.length && items[items.length-1] !== "..") items.pop();
    else if (part && part !== ".") items.push(part);
    return items;
  }, []);
  const source = parts(`${from}/${path}`), target = parts(to);
  let shared = 0;
  while (shared < source.length && shared < target.length && source[shared] === target[shared]) shared++;
  return [...Array(target.length-shared).fill(".."), ...source.slice(shared)].join("/") || ".";
}
export function pasteFragment(graph: Graph, fragment: Fragment, anchor?: {x: number; y: number}): {graph: Graph; ids: string[]} {
  if (!fragment.nodes.length) return {graph, ids: []};
  if (graph.nodes.length + fragment.nodes.length > 1000) throw Error("画布最多支持 1000 个节点。");
  const next = clone(graph), ids = new Map<string, string>();
  const used = new Set(next.nodes.flatMap(n => [n.id, String(n.params.output || "")]));
  const offset = anchor ? {x: anchor.x - Math.min(...fragment.nodes.map(n => n.position.x)), y: anchor.y - Math.min(...fragment.nodes.map(n => n.position.y))} : {x: 48, y: 48};
  for (const original of fragment.nodes) {
    const node = clone(original);
    const prefix = original.id.slice(0, 60);
    let index = 1, id = `${prefix}_copy${index}`;
    while (used.has(id) || used.has(`${id}_out`)) id = `${prefix}_copy${++index}`;
    used.add(id); used.add(`${id}_out`); ids.set(original.id, id);
    node.id = id; node.position = {x: node.position.x + offset.x, y: node.position.y + offset.y};
    if (node.kind === "source" && node.source && fragment.base_dir !== undefined)
      node.source.path = rebaseSource(node.source.path, fragment.base_dir, graph.base_dir);
    if (node.kind === "operator" && "output" in node.params) node.params.output = `${id}_out`;
    next.nodes.push(node);
  }
  for (const edge of fragment.edges) if (ids.has(edge.source) && ids.has(edge.target))
    next.edges.push({...clone(edge), id: `edge_${crypto.randomUUID()}`, source: ids.get(edge.source)!, target: ids.get(edge.target)!});
  // A pasted node is independent of the saved route boundary until explicitly
  // exposed in the interface editor; no external wires or retention names leak.
  const config = executionConfig(next), targets = {...config.node_targets}, locations = {...config.file_locations};
  for (const [oldId, newId] of ids) {
    if (fragment.node_targets?.[oldId]) targets[newId] = clone(fragment.node_targets[oldId]);
    for (const [key, target] of Object.entries(fragment.file_locations || {})) {
      if (key.startsWith(`${oldId}.params.`) || key.startsWith(`${oldId}.source.args.`)) locations[newId + key.slice(oldId.length)] = clone(target);
    }
  }
  return {graph: withExecution(next, {node_targets: targets, file_locations: locations}), ids: [...ids.values()]};
}
