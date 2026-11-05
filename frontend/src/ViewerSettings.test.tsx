import {isValidElement, type ReactNode} from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {ViewerSettings} from './ViewerSettings';
import {api} from './api';
import type {ViewerCatalog} from './viewerTypes';

const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0}));
vi.mock('react', async original => {
  const actual = await original<typeof import('react')>();
  return {...actual, useEffect: () => {}, useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = typeof initial === 'function' ? initial() : initial;
    return [hooks.values[index], (value: unknown) => {hooks.values[index] = value;}];
  }};
});
vi.mock('./api', () => ({api:{viewers:vi.fn(), defaultViewer:vi.fn(), configureViewer:vi.fn()}}));
type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  return isValidElement<Record<string, unknown>>(node) ? [node, ...elements(node.props.children as ReactNode)] : [];
}
function text(node: ReactNode): string {
  if (Array.isArray(node)) return node.map(text).join('');
  if (isValidElement<Record<string, unknown>>(node)) return text(node.props.children as ReactNode);
  return typeof node === 'string' ? node : '';
}
const catalog: ViewerCatalog = {defaults:{},viewers:[{id:'juicebox',name:'Juicebox',kind:'desktop',mode:'manual',extensions:['.hic'],domain:'Hi-C',status:'not_found',available:false,executable:null,notes:'',source:''}]};
function render() {hooks.cursor=0; return ViewerSettings({onBusyChange:()=>{}});}
function find(label: string) {return elements(render()).find(e => e.props['aria-label'] === label)!;}
function submit() {(elements(render()).find(e => e.type === 'form')!.props.onSubmit as (event: unknown)=>void)({preventDefault(){}});}
beforeEach(() => {hooks.values=[catalog,'',false,'','','.hic','']; hooks.cursor=0; vi.clearAllMocks();});
describe('viewer preferences', () => {
  it('persists a chosen format default without editing workflow state', async () => {
    vi.mocked(api.defaultViewer).mockResolvedValue({...catalog,defaults:{'.hic':'juicebox'}});
    (find('默认查看器').props.onChange as (e: unknown)=>void)({target:{value:'juicebox'}}); submit();
    await vi.waitFor(() => expect(text(render())).toContain('默认打开方式已保存'));
    expect(api.defaultViewer).toHaveBeenCalledExactlyOnceWith('.hic','juicebox');
    expect(find('已保存的打开方式')).toBeDefined();
  });
  it('restores automatic selection by clearing a saved default', async () => {
    hooks.values[0]={...catalog,defaults:{'.hic':'juicebox'}};
    vi.mocked(api.defaultViewer).mockResolvedValue(catalog);
    (find('清除 .hic 默认打开方式').props.onClick as ()=>void)();
    await vi.waitFor(() => expect(api.defaultViewer).toHaveBeenCalledExactlyOnceWith('.hic',null));
    await vi.waitFor(() => expect(text(render())).toContain('已恢复自动选择'));
  });
  it('keeps failures visible without claiming a save', async () => {
    vi.mocked(api.defaultViewer).mockRejectedValue(new Error('Cannot save preferences'));
    submit(); await vi.waitFor(() => expect(text(render())).toContain('Cannot save preferences'));
    expect(text(render())).not.toContain('已保存');
  });
  it('saves program locations through the shared profile service', async () => {
    vi.mocked(api.configureViewer).mockResolvedValue(catalog);
    const row = elements(render()).find(e => typeof e.type === 'function' && e.props.viewer)!;
    await (row.props.save as (id:string,path:string)=>Promise<void>)('juicebox','C:\\Apps\\Juicebox.exe');
    expect(api.configureViewer).toHaveBeenCalledExactlyOnceWith('juicebox','C:\\Apps\\Juicebox.exe');
    expect(text(render())).toContain('程序位置已保存');
  });
});
