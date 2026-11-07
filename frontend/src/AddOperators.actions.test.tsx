import {isValidElement, type ReactNode} from 'react';
import {beforeEach, expect, it, vi} from 'vitest';
import {AddOperators} from './AddOperators';
import {api} from './api';
import type {Graph} from './types';

const hooks=vi.hoisted(()=>({values:[] as unknown[], cursor:0}));
vi.mock('react',async original=>({...await original<typeof import('react')>(),useEffect:()=>{},useRef:()=>({current:null}),useState:(initial:unknown)=>{
  const i=hooks.cursor++; if(!(i in hooks.values))hooks.values[i]=initial;
  return [hooks.values[i],(next:unknown)=>{hooks.values[i]=typeof next==='function'?next(hooks.values[i]):next;}];
}}));
vi.mock('./api',()=>({api:{workflows:vi.fn(),importWorkflow:vi.fn(),saveWorkflow:vi.fn(),registerRoutes:vi.fn()}}));
const onChanged=vi.fn(async()=>{}),onPending=vi.fn(),onError=vi.fn(),onMessage=vi.fn();
type Element={type:unknown;props:Record<string,unknown>};
function elements(node:ReactNode):Element[] {
  if(Array.isArray(node))return node.flatMap(elements);
  if(!isValidElement<Record<string,unknown>>(node))return [];
  return [node,...elements(node.props.children as ReactNode)];
}
function render(){hooks.cursor=0;return AddOperators({state:{generation:null,packages:[],descriptors:[]},busy:false,onChanged,onPending,onError,onMessage,onPackage:()=>{},onRefresh:()=>{}});}
function triggerFiles(files: unknown[]) {
  const field=elements(render()).find(n=>n.type==='input'&&n.props.type==='file')!;
  (field.props.onChange as Function)({target:{files,value:'fake'}});
}
const graph:Graph={schema_version:2,name:'Imported',base_dir:'.',nodes:[],edges:[],memory:{enabled:true}};
beforeEach(()=>{hooks.values=[];hooks.cursor=0;vi.clearAllMocks();vi.mocked(api.workflows).mockResolvedValue([]);
  vi.mocked(api.saveWorkflow).mockResolvedValue({id:'saved',version:1,graph,updated_at:''});vi.mocked(api.registerRoutes).mockResolvedValue([]);});
it('imports a bundle, saves its graph and registers it without opening or running a canvas',async()=>{
  vi.mocked(api.importWorkflow).mockResolvedValue(graph);
  const file={name:'route.operon.zip'};triggerFiles([file]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(api.importWorkflow).toHaveBeenCalledWith(file);expect(vi.mocked(api.saveWorkflow).mock.calls[0][0]).toMatchObject(graph);
  expect(api.registerRoutes).toHaveBeenCalledWith(['saved']);expect(onChanged).toHaveBeenCalledOnce();
});
it('keeps successfully saved imports selected when a later file fails',async()=>{
  triggerFiles([{name:'one.json',text:async()=>JSON.stringify(graph)},{name:'bad.json',text:async()=>'{broken'}]);
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(hooks.values[1]).toEqual(['saved']);expect(api.registerRoutes).not.toHaveBeenCalled();
  expect(onError).toHaveBeenCalled();expect(onChanged).toHaveBeenCalledOnce();
});
it('registers all selected saved workflows in a single request',async()=>{
  hooks.values=[[],['one','two'],'',false];
  const button=elements(render()).find(n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children.includes('添加到算子库'))!;
  expect(button.props.disabled).toBe(false);(button.props.onClick as Function)();
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(api.registerRoutes).toHaveBeenCalledExactlyOnceWith(['one','two']);expect(api.saveWorkflow).not.toHaveBeenCalled();
});
it('reports a rejected workflow without clearing its selection or claiming success',async()=>{
  hooks.values=[[],['incomplete'],'',false];
  vi.mocked(api.registerRoutes).mockRejectedValue(new Error('PCA needs 1 input.'));
  const button=elements(render()).find(n=>n.type==='button'&&Array.isArray(n.props.children)&&n.props.children.includes('添加到算子库'))!;
  (button.props.onClick as Function)();
  await vi.waitFor(()=>expect(onPending).toHaveBeenLastCalledWith(false));
  expect(onError).toHaveBeenLastCalledWith('路线未添加：PCA needs 1 input.');
  expect(hooks.values[1]).toEqual(['incomplete']);
  expect(onMessage).not.toHaveBeenCalledWith('路线算子已添加，即刻可用。');
  expect(onChanged).toHaveBeenCalledOnce();
});
