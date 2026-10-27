import {isValidElement, type ReactNode} from 'react';
import {beforeEach, describe, expect, it, vi} from 'vitest';
import {api, ApiError} from './api';
import {RemotePanel} from './RemotePanel';
import type {RemoteInfo, RemoteProfile, RemoteStatus} from './types';

// Drive the actual panel callbacks with retained hook state. The project runs
// Vitest in Node, so static markup coverage lives in RemotePanel.test.tsx.
const hooks = vi.hoisted(() => ({values: [] as unknown[], cursor: 0}));
vi.mock('react', async importOriginal => {
  const actual = await importOriginal<typeof import('react')>();
  return {...actual, useEffect: () => {}, useState: (initial: unknown) => {
    const index = hooks.cursor++;
    if (!(index in hooks.values)) hooks.values[index] = typeof initial === 'function' ? initial() : initial;
    return [hooks.values[index], (next: unknown) => {
      hooks.values[index] = typeof next === 'function' ? next(hooks.values[index]) : next;
    }];
  }};
});
vi.mock('./api', async importOriginal => {
  const actual = await importOriginal<typeof import('./api')>();
  return {...actual, api: {saveRemote: vi.fn(), connectRemote: vi.fn(), installRemote: vi.fn(), refreshRemote: vi.fn(), trustRemote: vi.fn()}};
});

type Element = {type: unknown; props: Record<string, unknown>};
function elements(node: ReactNode): Element[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Record<string, unknown>>(node)) return [];
  return [node, ...elements(node.props.children as ReactNode)];
}
function text(node: ReactNode): string {
  if (Array.isArray(node)) return node.map(text).join('');
  if (isValidElement<Record<string, unknown>>(node)) return text(node.props.children as ReactNode);
  return typeof node === 'string' || typeof node === 'number' ? String(node) : '';
}
function trigger(element: Element, event: string, value: unknown = {}) {
  (element.props[event] as (value: unknown) => void)(value);
}

const profile: RemoteProfile = {id: 'server-a', name: 'Compute', host: 'example.org', port: 22, username: 'user', auth: 'password',
  key_path: '', python: 'python3', app_dir: '', workspace: '', mode: 'exec', menu_choice: '', environment: 'managed', managed_root: ''};
const info = {version: '0.7.1', system: 'linux', catalog: {schema_version: 1, operators: []}, tools: {}} as unknown as RemoteInfo;
const onUpdate = vi.fn(async () => {}), onSelect = vi.fn();
let servers: RemoteStatus[];
function render() {hooks.cursor = 0; return RemotePanel({servers, active: profile.id!, onUpdate, onSelect, onClose: () => {}});}
function find(type: string, label?: string) {
  const match = elements(render()).find(node => node.type === type && (label === undefined || text(node.props.children as ReactNode) === label));
  expect(match, `${type}: ${label || ''}`).toBeDefined();
  return match!;
}
function setPassword(value: string) {
  const input = elements(render()).find(node => node.type === 'input' && node.props.type === 'password')!;
  trigger(input, 'onChange', {target: {value}});
}
function start(action: 'connect' | 'install') {
  if (action === 'connect') trigger(find('form'), 'onSubmit', {preventDefault() {}});
  else trigger(find('button', '安装 / 升级服务端'), 'onClick', {currentTarget: {form: {reportValidity: () => true}}});
}
async function updated(count = 1) {await vi.waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(count));}

beforeEach(() => {
  hooks.values = []; hooks.cursor = 0; vi.clearAllMocks();
  servers = [{profile: {...profile}, connected: false}];
  vi.mocked(api.saveRemote).mockImplementation(async value => ({...value, id: profile.id}));
  vi.mocked(api.connectRemote).mockResolvedValue(info);
  vi.mocked(api.installRemote).mockResolvedValue(info);
  vi.mocked(api.refreshRemote).mockResolvedValue(info);
  vi.mocked(api.trustRemote).mockResolvedValue({});
});

describe('remote connection actions', () => {
  it('connects without installing or refreshing and keeps credentials out of the saved profile', async () => {
    setPassword('session-only'); start('connect'); await updated();
    expect(api.connectRemote).toHaveBeenCalledExactlyOnceWith('server-a', {password: 'session-only', passphrase: ''});
    expect(api.installRemote).not.toHaveBeenCalled(); expect(api.refreshRemote).not.toHaveBeenCalled();
    expect(api.saveRemote).toHaveBeenCalledExactlyOnceWith(profile);
    expect(JSON.stringify(vi.mocked(api.saveRemote).mock.calls)).not.toContain('session-only');
    expect(elements(render()).find(node => node.type === 'input' && node.props.type === 'password')?.props.value).toBe('');
    expect(onSelect).toHaveBeenCalledExactlyOnceWith('server-a');
  });
  it('installs only after the explicit maintenance action', async () => {
    setPassword('session-only'); start('install'); await updated();
    expect(api.installRemote).toHaveBeenCalledExactlyOnceWith('server-a', {password: 'session-only', passphrase: ''});
    expect(api.connectRemote).not.toHaveBeenCalled();
  });
  it('validates required profile fields before installation', () => {
    trigger(find('button', '安装 / 升级服务端'), 'onClick', {currentTarget: {form: {reportValidity: () => false}}});
    expect(api.saveRemote).not.toHaveBeenCalled(); expect(api.installRemote).not.toHaveBeenCalled();
  });
  it.each(['connect', 'install'] as const)('preserves %s across host trust confirmation', async action => {
    const request = action === 'install' ? api.installRemote : api.connectRemote;
    vi.mocked(request).mockRejectedValueOnce(new ApiError('trust required', undefined, 409, 'host_key_required', {fingerprint: 'SHA256:test', changed: true}));
    setPassword('session-only'); start(action); await updated();
    expect(text(render())).toContain('服务器指纹已变化');
    expect(find('button', '连接服务器').props.disabled).toBe(true);
    trigger(find('button', action === 'install' ? '信任并安装 / 升级' : '信任并连接'), 'onClick'); await updated(2);
    expect(api.trustRemote).toHaveBeenCalledExactlyOnceWith('server-a', 'SHA256:test');
    expect(request).toHaveBeenCalledTimes(2);
    expect(request).toHaveBeenLastCalledWith('server-a', {password: 'session-only', passphrase: ''});
    expect(api.saveRemote).toHaveBeenCalledTimes(1);
    expect(action === 'install' ? api.connectRemote : api.installRemote).not.toHaveBeenCalled();
  });
  it('exposes installation on a missing server without automatically installing', async () => {
    vi.mocked(api.connectRemote).mockRejectedValueOnce(new ApiError('not installed', undefined, 409, 'server_not_installed'));
    start('connect'); await updated();
    expect(text(render())).toContain('未找到 BioPipe 服务端，请先安装服务端。');
    expect(elements(render()).find(node => node.props.className === 'remote-maintenance')?.props.open).toBe(true);
    expect(api.installRemote).not.toHaveBeenCalled(); expect(onSelect).not.toHaveBeenCalled();
  });
  it.each(['server_incompatible', 'handshake_incompatible', 'capability_missing'])('offers explicit upgrade for %s without retrying installation', async code => {
    vi.mocked(api.connectRemote).mockRejectedValueOnce(new ApiError('', undefined, 409, code));
    start('connect'); await updated();
    expect(text(render())).toContain('服务端不兼容，请安装 / 升级服务端后重试。');
    expect(api.installRemote).not.toHaveBeenCalled();
  });
  it.each(['', '操作未完成，请重试。'])('requires a one-time upgrade when handshake guidance is absent (%s)', async message => {
    vi.mocked(api.connectRemote).mockRejectedValueOnce(new ApiError(message, undefined, 409, 'handshake_required'));
    start('connect'); await updated();
    expect(text(render())).toContain('此服务端需要一次性升级后重新连接。');
    expect(elements(render()).find(node => node.props.className === 'remote-maintenance')?.props.open).toBe(true);
    expect(api.installRemote).not.toHaveBeenCalled();
  });
  it.each(['server_incompatible', 'handshake_incompatible', 'capability_missing', 'handshake_required'])('preserves server recovery instructions for %s', async code => {
    const message = '服务端仍有任务运行，请先等待任务结束，再升级并重启服务端后重新连接。';
    vi.mocked(api.connectRemote).mockRejectedValueOnce(new ApiError(message, undefined, 409, code));
    start('connect'); await updated();
    expect(text(render())).toContain(message);
    expect(elements(render()).find(node => node.props.className === 'remote-maintenance')?.props.open).toBe(true);
    expect(api.installRemote).not.toHaveBeenCalled();
    expect(api.connectRemote).toHaveBeenCalledTimes(1);
  });
  it('keeps manually specified environments on the manual recovery path', async () => {
    servers = [{profile: {...profile, environment: 'existing', app_dir: '/code', python: '/env/bin/python', workspace: '/work'}, connected: false}];
    vi.mocked(api.connectRemote).mockRejectedValueOnce(new ApiError('not installed', undefined, 409, 'server_not_installed'));
    start('connect'); await updated();
    expect(text(render())).toContain('未找到 BioPipe 服务端，请检查 BioPipe 目录与 Python 路径。');
    expect(text(render())).not.toContain('安装 / 升级服务端');
    expect(api.installRemote).not.toHaveBeenCalled();
  });
  it('refreshes only a connected server without installing, reconnecting or resaving credentials', async () => {
    expect(text(render())).not.toContain('刷新算子与依赖');
    servers = [{profile, connected: true, info}];
    trigger(find('button', '刷新算子与依赖'), 'onClick'); await updated();
    expect(api.refreshRemote).toHaveBeenCalledExactlyOnceWith('server-a');
    expect(api.installRemote).not.toHaveBeenCalled(); expect(api.connectRemote).not.toHaveBeenCalled(); expect(api.saveRemote).not.toHaveBeenCalled();
  });
  it('shows an actionable refresh failure without reconnecting automatically', async () => {
    servers = [{profile, connected: true, info}];
    const message = '旧服务端尚不支持握手，请等待现有任务结束，再升级并重启服务端。';
    vi.mocked(api.refreshRemote).mockRejectedValueOnce(new ApiError(message, undefined, 409, 'handshake_required'));
    trigger(find('button', '刷新算子与依赖'), 'onClick'); await updated();
    expect(text(render())).toContain(message);
    expect(elements(render()).find(node => node.props.className === 'remote-maintenance')?.props.open).toBe(true);
    expect(api.connectRemote).not.toHaveBeenCalled(); expect(api.installRemote).not.toHaveBeenCalled();
    expect(find('button', '刷新算子与依赖').props.disabled).toBe(false);
  });
});
