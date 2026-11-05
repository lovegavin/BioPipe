import {isValidElement, type ReactNode} from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {ResultViewers, type Viewer} from './ResultViewers';
import {api} from './api';

const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0}));
vi.mock('react', async original => {
  const actual = await original<typeof import('react')>();
  function state(initial: unknown) {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = initial;
    return [hooks.values[index], (value: unknown) => {hooks.values[index] = value;}];
  }
  return {...actual, useEffect: () => {}, useState: state, useRef: (initial: unknown) => state({current: initial})[0]};
});
vi.mock('./api', () => ({api:{openViewer:vi.fn(),artifactViewers:vi.fn(),configureViewer:vi.fn(),prepareViewer:vi.fn(),viewers:vi.fn()}}));
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
const desktop = {id:'igv',name:'IGV',kind:'desktop',mode:'file',available:true,status:'ready',notes:'',executable:null,source:''} as Viewer;
const list = [desktop,{...desktop,id:'missing',name:'Missing',available:false,status:'not_found'},
  {...desktop,id:'manual',name:'Manual',mode:'manual'},
  {...desktop,id:'web',name:'Web',kind:'web',url:'https://example.org'}] as Viewer[];
const onSettings = vi.fn();
function render() {hooks.cursor=0;return ResultViewers({job:'job',artifact:'artifact',role:'data',onSettings});}
function click(label: string) {
  const button = elements(render()).find(e => e.type === 'button' && (text(e.props.children as ReactNode).startsWith(label) || e.props['aria-label'] === label));
  expect(button).toBeDefined(); (button!.props.onClick as () => void)();
}
beforeEach(() => {
  hooks.values = [true,{viewers:list,default_viewer:'igv',default_source:'configured'},false,'','','']; hooks.cursor=0;
  vi.clearAllMocks(); vi.mocked(api.artifactViewers).mockResolvedValue({viewers:list,default_viewer:'igv',default_source:'configured'});
  vi.mocked(api.openViewer).mockResolvedValue({status:'started',mode:'file',path:'result.bed'});
});
describe('desktop-first result handoff', () => {
  it('launches only the selected retained role and never submits a pipeline', async () => {
    click('IGV'); await vi.waitFor(() => expect(text(render())).toContain('已发送打开请求'));
    expect(api.openViewer).toHaveBeenCalledExactlyOnceWith('job','artifact','data','igv');
  });
  it('marks unavailable applications and leaves web import an explicit link', () => {
    const all = elements(render());
    expect(all.find(e => e.type === 'button' && text(e.props.children as ReactNode).startsWith('Missing'))?.props.disabled).toBe(true);
    const web = all.find(e => e.type === 'a'); expect(web?.props.href).toBe('https://example.org');
    expect(web?.props.rel).toBe('noreferrer'); expect(text(web?.props.children as ReactNode)).toContain('手动导入');
    expect(api.openViewer).not.toHaveBeenCalled();
  });
  it('distinguishes manual launch from file loading', async () => {
    vi.mocked(api.openViewer).mockResolvedValue({status:'started',mode:'manual',path:'result.hic'});
    click('Manual'); await vi.waitFor(() => expect(text(render())).toContain('请在软件中打开下方文件'));
    expect(elements(render()).find(e => e.props['aria-label'] === '结果文件位置')?.props.value).toBe('result.hic');
  });
  it('shows launch failures without claiming success', async () => {
    vi.mocked(api.openViewer).mockRejectedValue(new Error('Application missing'));
    click('IGV'); await vi.waitFor(() => expect(text(render())).toContain('Application missing'));
    expect(text(render())).not.toContain('已发送打开请求');
  });
  it('moves configuration into central settings', () => {
    click('管理打开方式');
    expect(onSettings).toHaveBeenCalledOnce();
    expect(elements(render()).some(e => e.type === 'form')).toBe(false);
    expect(api.configureViewer).not.toHaveBeenCalled();
  });
  it('resolves the current saved default on the service when Open is clicked', async () => {
    click('打开');
    await vi.waitFor(() => expect(api.openViewer).toHaveBeenCalledExactlyOnceWith('job','artifact','data',undefined));
  });
});
