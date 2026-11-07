import {api} from './api';
import {makeNode} from './graph';
import type {Graph, GraphNode, ScriptSnapshot} from './types';

export const isScriptFile = (name: string) => /\.(?:py|r|c|cc|cpp)$/i.test(name);
export const fileDropEffect = (types: readonly string[]): 'copy' | 'move' => types.includes('Files') ? 'copy' : 'move';
export function makeScriptNode(graph: Graph, script: ScriptSnapshot, position: {x: number; y: number}): GraphNode {
  const node = makeNode(graph, undefined, position);
  const properties = script.parameters_schema.properties as Record<string, {default?: unknown}> | undefined;
  return {id: node.id, kind: 'script', title: script.filename.replace(/\.[^.]+$/, ''), position,
    input_count: Object.keys(script.inputs).length, script,
    params: Object.fromEntries(Object.entries(properties || {}).filter(([, value]) => value.default !== undefined).map(([key, value]) => [key, structuredClone(value.default)]))};
}

/** Resolve the complete drop before a single canvas commit; sibling data files stay together. */
export async function droppedNodes(files: File[], graph: Graph, position: {x: number; y: number}): Promise<GraphNode[]> {
  const scriptFiles = files.filter(file => isScriptFile(file.name));
  const dataFiles = files.filter(file => !isScriptFile(file.name));
  const nodes: GraphNode[] = [];
  const nextGraph = () => ({...graph, nodes: [...graph.nodes, ...nodes]});
  const nextPosition = () => ({x: position.x + nodes.length * 36, y: position.y + nodes.length * 48});
  for (const file of scriptFiles) {
    const result = await api.inspectScript({filename: file.name, code: await file.text()});
    nodes.push(makeScriptNode(nextGraph(), result.script, nextPosition()));
  }
  if (dataFiles.length) {
    const result = await api.uploadFiles(dataFiles, graph.base_dir);
    const node = makeNode(nextGraph(), undefined, nextPosition());
    nodes.push({...node, title: result.filename.replace(/\.(?:gz|bz2|xz)$/i, '').replace(/\.[^.]+$/, ''),
      source: {...result.source, location: {kind: 'local'}}});
  }
  return nodes;
}
