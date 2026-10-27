import {isValidElement, type ReactNode} from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {Results} from './Results';
import type {Job} from './types';

const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0}));
vi.mock('react', async original => {
  const actual = await original<typeof import('react')>();
  function state(initial: unknown) {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = typeof initial === 'function' ? initial() : initial;
    return [hooks.values[index], (value: unknown) => {hooks.values[index] = typeof value === 'function' ? value(hooks.values[index]) : value;}];
  }
  return {...actual, useEffect: () => {}, useState: state, useRef: (initial: unknown) => state({current: initial})[0]};
});

type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  return isValidElement<Record<string, unknown>>(node) ? [node, ...elements(node.props.children as ReactNode)] : [];
}
function text(node: ReactNode): string {
  if (Array.isArray(node)) return node.map(text).join('');
  if (isValidElement<Record<string, unknown>>(node)) return text(node.props.children as ReactNode);
  return typeof node === 'string' || typeof node === 'number' ? String(node) : '';
}
const history: Job[] = ['First run','Second run'].map((name,i) => ({id:`job-${i}`,name,status:'complete',created_at:'2026-10-27T00:00:00Z'}));
const onJob = vi.fn<(id: string) => Promise<void>>(), onTab = vi.fn(), onRestore = vi.fn(), onError = vi.fn();
function render() {hooks.cursor=0;return Results({job:null,events:[],history,tab:'history',onJob,onTab,onRestore,onError,collapsed:false,onToggle:()=>{},stale:false});}
function click(label: string, index=0) {
  const buttons=elements(render()).filter(e=>e.type==='button' && (text(e.props.children as ReactNode)===label || e.props['aria-label']===label));
  expect(buttons[index]).toBeDefined();(buttons[index].props.onClick as ()=>void)();
}
beforeEach(()=>{hooks.values=[];hooks.cursor=0;vi.clearAllMocks();onJob.mockResolvedValue();});
describe('history result navigation',()=>{
  it('opens results without restoring the canvas',async()=>{
    click('查看结果',1);await vi.waitFor(()=>expect(onTab).toHaveBeenCalledWith('results'));
    expect(onJob).toHaveBeenCalledWith('job-1');expect(onRestore).not.toHaveBeenCalled();
  });
  it('opens the selected run log directly',async()=>{
    click('查看日志');await vi.waitFor(()=>expect(onTab).toHaveBeenCalledWith('logs'));
    expect(onJob).toHaveBeenCalledWith('job-0');expect(onRestore).not.toHaveBeenCalled();
  });
  it('makes the run name open results and waits for successful loading',async()=>{
    let finish!:()=>void;onJob.mockReturnValue(new Promise(resolve=>{finish=resolve;}));
    click('查看结果 First run');expect(onTab).not.toHaveBeenCalled();finish();
    await vi.waitFor(()=>expect(onTab).toHaveBeenCalledWith('results'));
  });
  it('keeps the history visible if the server cannot be reached',async()=>{
    onJob.mockRejectedValue(new Error('请先连接服务器。'));click('查看结果');
    await vi.waitFor(()=>expect(onError).toHaveBeenCalledWith('请先连接服务器。'));
    expect(onTab).not.toHaveBeenCalled();
  });
  it('does not apply an older navigation after a more recent click',async()=>{
    let first!:()=>void;onJob.mockImplementation(id=>id==='job-0'?new Promise(resolve=>{first=resolve;}):Promise.resolve());
    click('查看结果');click('查看日志',1);
    await vi.waitFor(()=>expect(onTab).toHaveBeenCalledExactlyOnceWith('logs'));
    first();await Promise.resolve();expect(onTab).toHaveBeenCalledExactlyOnceWith('logs');
  });
});
