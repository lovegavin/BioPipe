import {isValidElement, type ReactNode} from 'react';
import {beforeEach, expect, it, vi} from 'vitest';
import {CollaborationActivity, mergeActivity} from './CollaborationActivity';
import type {CanvasEvent} from './agentBridge';
import {api} from './api';

const hooks=vi.hoisted(()=>({values:[] as unknown[],cursor:0}));
vi.mock('react',async original=>{
  const actual=await original<typeof import('react')>();
  return {...actual,useState:(initial:unknown)=>{
    const index=hooks.cursor++;
    if(!(index in hooks.values))hooks.values[index]=initial;
    return [hooks.values[index],(value:unknown)=>{hooks.values[index]=typeof value==='function'?value(hooks.values[index]):value;}];
  }};
});
type Element={type:unknown;props:Record<string,unknown>};
function elements(node:ReactNode):Element[]{return Array.isArray(node)?node.flatMap(elements):isValidElement<Record<string,unknown>>(node)?[node,...elements(node.props.children as ReactNode)]:[];}
function text(node:ReactNode):string{return Array.isArray(node)?node.map(text).join(''):isValidElement<Record<string,unknown>>(node)?text(node.props.children as ReactNode):typeof node==='string'||typeof node==='number'?String(node):'';}
const event:CanvasEvent={seq:1,time:'2026-11-06T13:00:00Z',actor:'agent:test',type:'graph.changed',revision:1,
  transaction_id:'tx1',change_count:1,affected:[{document_id:'main',nodes:['pca']}],
  changes:[{document_id:'main',path:['nodes','pca','params','n_components'],before:'2',after:'3',before_exists:true,after_exists:true}]};
const locate=vi.fn(),undo=vi.fn();
function render(){hooks.cursor=0;return CollaborationActivity({events:[event],sessionId:'session',onLocate:locate,onUndo:undo});}
function click(label:string){const button=elements(render()).find(item=>item.type==='button'&&text(item.props.children as ReactNode)===label);expect(button).toBeDefined();(button!.props.onClick as ()=>void)();}
beforeEach(()=>{hooks.values=[];hooks.cursor=0;vi.restoreAllMocks();locate.mockReset();undo.mockReset().mockResolvedValue(undefined);});
it('deduplicates re-delivered events and handles retained-history reset',()=>{
  expect(mergeActivity([event],[event])).toEqual([event]);
  expect(mergeActivity([event],[],true)).toEqual([]);
  expect(mergeActivity([], [{...event,type:'selection.changed'}])).toEqual([]);
});
it('shows real parameter differences and explicitly locates or reverses a transaction',async()=>{
  vi.spyOn(api,'agent').mockResolvedValue({changes:event.changes,total:1,next_offset:1});
  click('协作记录test');
  click('查看差异');
  await vi.waitFor(()=>expect(text(render())).toContain('n_components'));
  expect(text(render())).toContain('− 2');expect(text(render())).toContain('+ 3');
  click('已修改 1 项');expect(locate).toHaveBeenCalledWith('main','pca');
  click('撤销这次修改');await vi.waitFor(()=>expect(undo).toHaveBeenCalledWith('main','tx1'));
});
it('shows conflicts without pretending the undo succeeded',async()=>{
  undo.mockRejectedValue(new Error('Later edits overlap this transaction'));
  click('协作记录test');click('撤销这次修改');
  await vi.waitFor(()=>expect(text(render())).toContain('Later edits overlap this transaction'));
});
