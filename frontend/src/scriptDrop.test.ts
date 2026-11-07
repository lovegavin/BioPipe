import {beforeEach, expect, it, vi} from 'vitest';
import {api} from './api';
import {droppedNodes, fileDropEffect, isScriptFile, makeScriptNode} from './scriptDrop';
import {inputCount, outputCount, retainedOutputs, runSignature, specFor} from './graph';
import {copyFragment, parseFragment, pasteFragment} from './editing';
import {fileFormats, portTemplate} from './PortTemplateMenu';
import type {Graph, ScriptSnapshot} from './types';

const graph: Graph = {schema_version: 2, name: 'script', base_dir: '.', nodes: [], edges: [], memory: {enabled: true}};
const script: ScriptSnapshot = {language: 'python', filename: 'filter.py', code: 'threshold = 3\n', code_sha: 'code',
  inputs: {data: {kind: 'file', format: 'csv'}}, outputs: {result: {kind: 'file', format: 'csv'}}, dependencies: [],
  parameters_schema: {type: 'object', properties: {threshold: {type: 'integer', default: 3}}}};
beforeEach(() => vi.restoreAllMocks());
it('accepts copy-only OS file drags while retaining canvas operator moves', () => {
  expect(fileDropEffect(['Files'])).toBe('copy');
  expect(fileDropEffect(['Files', 'text/uri-list'])).toBe('copy');
  expect(fileDropEffect(['application/operon'])).toBe('move');
});
it('recognizes scripts without treating gzip data as code and freezes values on drop', async () => {
  vi.spyOn(api, 'inspectScript').mockResolvedValue({script, candidates: []});
  const upload = vi.spyOn(api, 'uploadFiles').mockResolvedValue({source: {reader: 'CsvReader', path: 'assets/input.csv', dims: [], labels: {}, args: {}}, filename: 'input.csv', reader: 'CsvReader', files: []});
  const files = [{name: 'filter.py', text: async () => script.code}, {name: 'input.csv'}] as File[];
  const nodes = await droppedNodes(files, graph, {x: 10, y: 20});
  expect(nodes.map(node => node.kind)).toEqual(['script', 'source']);
  expect(nodes[0].params).toEqual({threshold: 3});
  expect(nodes[0].source).toBeUndefined();
  expect(nodes[1].source?.location).toEqual({kind: 'local'});
  expect(nodes[0].id).not.toBe(nodes[1].id);
  expect(upload).toHaveBeenCalledWith([files[1]], '.');
  expect(isScriptFile('trim.R')).toBe(true); expect(isScriptFile('reads.py.gz')).toBe(false);
});
it('keeps sibling data files in one upload batch and refuses invalid scripts before a data upload', async () => {
  const upload = vi.spyOn(api, 'uploadFiles');
  vi.spyOn(api, 'inspectScript').mockRejectedValue(new Error('Invalid Python syntax'));
  await expect(droppedNodes([{name: 'bad.py', text: async () => 'syntax!'}, {name: 'input.csv'}] as File[], graph, {x: 0, y: 0})).rejects.toThrow('Invalid Python');
  expect(upload).not.toHaveBeenCalled();
  upload.mockResolvedValue({source: {path: 'sample.bed', dims: [], labels: {}, args: {}}, filename: 'sample.bed', reader: 'PlinkReader', files: []});
  const siblings = ['sample.bed', 'sample.bim', 'sample.fam'].map(name => ({name})) as File[];
  await droppedNodes(siblings, graph, {x: 0, y: 0});
  expect(upload).toHaveBeenCalledWith(siblings, '.');
});
it('tracks scientific source edits and preserves script snapshots through copy/paste', () => {
  const node = makeScriptNode(graph, script, {x: 1, y: 2});
  const spec = specFor(node, {schema_version: 1, operators: []});
  expect([inputCount(node, spec), outputCount(node, spec)]).toEqual([1, 1]);
  expect(retainedOutputs(node, spec)).toEqual([node.id]);
  const current = {...graph, nodes: [node]};
  expect(runSignature(current)).not.toBe(runSignature({...graph, nodes: [{...node, script: {...script, code: 'threshold = 4', code_sha: 'changed'}}]}));
  const copied = pasteFragment(current, parseFragment(JSON.stringify(copyFragment(current, [node.id]))));
  expect(copied.graph.nodes[1].script).toEqual(script);
  expect(copied.graph.nodes[1].params).toEqual({threshold: 3});
});
it('only offers a file ABI for declared file formats; templates do not convert matrix semantics', () => {
  expect(fileFormats({kind: 'form', data_format: {logical_type: 'matrix', representations: ['file.csv']}})).toEqual([]);
  expect(fileFormats({kind: 'file', info: {representation: {const: 'pairs'}}})).toEqual(['pairs']);
  expect(fileFormats({kind: 'file', info: {representation: {const: '../bad'}}})).toEqual([]);
  for (const language of ['python', 'r', 'c', 'cpp'] as const) {
    const code = portTemplate(language, 'csv');
    expect(code).toContain('input: data file.csv'); expect(code).toContain('output: result file.csv');
    expect(code).toContain('--in-data'); expect(code).toContain('--out-result');
  }
  expect(() => portTemplate('python', 'csv\nprint(1)')).toThrow('declared');
});
