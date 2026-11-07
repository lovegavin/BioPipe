import {isValidElement, type ReactNode} from 'react';
import {beforeEach, expect, it, vi} from 'vitest';
import {ScriptInspector, ScriptLibrarySave, OperatorSource, scriptParameters, scriptReplacement} from './ScriptInspector';
import {api} from './api';
import type {GraphNode, NodePatch, ScriptSnapshot} from './types';

const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0}));
vi.mock('react', async original => {
  const actual = await original<typeof import('react')>();
  return {...actual, useEffect: () => {}, useRef: (value: unknown) => ({current: value}), useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = typeof initial === 'function' ? initial() : initial;
    return [hooks.values[index], (value: unknown) => {hooks.values[index] = typeof value === 'function' ? value(hooks.values[index]) : value;}];
  }};
});
type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {return Array.isArray(node) ? node.flatMap(elements) : isValidElement<Record<string, unknown>>(node) ? [node, ...elements(node.props.children as ReactNode)] : [];}
function text(node: ReactNode): string {return Array.isArray(node) ? node.map(text).join('') : isValidElement<Record<string, unknown>>(node) ? text(node.props.children as ReactNode) : typeof node === 'string' || typeof node === 'number' ? String(node) : '';}
const script: ScriptSnapshot = {language: 'python', filename: 'trim.py', code: 'threshold = 3\n', code_sha: 'a', inputs: {}, outputs: {result: {kind: 'file', format: 'csv'}}, dependencies: [], parameters_schema: {type: 'object', properties: {}}};
let node: GraphNode;
const onNode = vi.fn((_id: string, patch: NodePatch) => {node = {...node, ...(typeof patch === 'function' ? patch(node) : patch)};});
function render() {hooks.cursor = 0; return ScriptInspector({node, disabled: false, onNode});}
function click(label: string) {const button = elements(render()).find(item => item.type === 'button' && text(item.props.children as ReactNode) === label); expect(button).toBeDefined(); (button!.props.onClick as () => void)();}
beforeEach(() => {vi.restoreAllMocks(); hooks.values = []; hooks.cursor = 0; onNode.mockClear(); node = {id: 'script', kind: 'script', script, title: 'Trim', params: {}, input_count: 0, position: {x: 0, y: 0}};});
it('saves edited code only after static validation and commits extraction with frozen values atomically', async () => {
  vi.spyOn(api, 'inspectScript').mockResolvedValue({script, candidates: [{name: 'threshold', line: 1, schema: {type: 'integer', default: 3}}]});
  const extracted = {...script, code: 'threshold = values["threshold"]\n', code_sha: 'b', parameters_schema: {properties: {threshold: {type: 'integer'}}}};
  vi.spyOn(api, 'extractScript').mockResolvedValue({script: extracted, values: {threshold: 3}, bindings: {}});
  click('保存代码并检查');
  await vi.waitFor(() => expect(text(render())).toContain('threshold'));
  const checkbox = elements(render()).find(item => item.type === 'input' && item.props.type === 'checkbox');
  (checkbox!.props.onChange as (event: unknown) => void)({target: {checked: true}});
  click('提取到参数 JSON');
  await vi.waitFor(() => expect(node.script?.code_sha).toBe('b'));
  expect(node.params).toEqual({threshold: 3});
  expect(onNode).toHaveBeenCalledTimes(2);
});
it('does not replace code after a syntax error or concurrent code edit', async () => {
  vi.spyOn(api, 'inspectScript').mockRejectedValue(new Error('SyntaxError at line 2'));
  click('保存代码并检查');
  await vi.waitFor(() => expect(text(render())).toContain('SyntaxError'));
  expect(onNode).not.toHaveBeenCalled();
  expect(() => scriptReplacement({...node, script: {...script, code_sha: 'changed'}}, 'a', script)).toThrow('代码已被其他操作修改');
  expect(scriptReplacement({...node, params: {user: 9}}, 'a', script, {threshold: 3}).params).toEqual({user: 9, threshold: 3});
});
it('maps schema controls without inventing semantics and exposes native source as read-only', () => {
  expect(scriptParameters({...script, parameters_schema: {properties: {enabled: {type: 'boolean'}, method: {type: 'string', enum: ['a', 'b']}, columns: {type: 'array'}}}}).map(field => field.type)).toEqual(['boolean', 'choice', 'json']);
  hooks.cursor = 0;
  const tree = OperatorSource({route: {nodes: []}});
  const area = elements(tree).find(item => item.type === 'textarea');
  expect(area?.props.readOnly).toBe(true);
  expect(area?.props.value).toContain('nodes');
});
it('promotes an explicitly saved script into a chosen library category without running it', async () => {
  const catalog: import('./types').Catalog = {schema_version: 1, operators: [{id: 'user.trim', title: 'Trim', category: 'statistics',
    description: '', inputs_arity: 0, outputs: ['result'], output_parameter: null, resources: {memory_modes: ['full'], supports_cuda: false}, parameters: []}]};
  const published = vi.spyOn(api, 'publishScript').mockResolvedValue({id: 'user.trim', catalog});
  const changed = vi.fn();
  function renderSave() {hooks.cursor = 0; return ScriptLibrarySave({node, catalog, disabled: false, onCatalog: changed});}
  const select = elements(renderSave()).find(item => item.type === 'select');
  (select!.props.onChange as (event: unknown) => void)({target: {value: 'statistics'}});
  const button = elements(renderSave()).find(item => item.type === 'button');
  (button!.props.onClick as () => void)();
  await vi.waitFor(() => expect(changed).toHaveBeenCalledWith(catalog, 'user.trim'));
  expect(published).toHaveBeenCalledWith({script, operator_id: 'user.trim', title: 'Trim', category: 'statistics'});
  expect(text(renderSave())).toContain('已添加到算子库：user.trim');
});
