import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {RemotePanel} from './RemotePanel';
import type {RemoteInfo, RemoteStatus} from './types';

const props = {active: '', onUpdate: async () => {}, onSelect: () => {}, onClose: () => {}};
describe('server connection and maintenance', () => {
  it('defaults to an installed server with a separate collapsed installation action', () => {
    const html = renderToStaticMarkup(<RemotePanel {...props} servers={[]}/>);
    expect(html).toContain('value="managed" selected');
    expect(html).toContain('安装目录');
    expect(html).toContain('已安装的 BioPipe 服务端');
    expect(html).toContain('连接服务器');
    expect(html).toContain('安装 / 升级服务端');
    expect(html).toContain('<details class="remote-maintenance">');
    expect(html).not.toContain('自动部署');
    expect(html).not.toContain('刷新算子与依赖');
    expect(html).not.toContain('>Python</span>');
    expect(html).not.toContain('>BioPipe 目录</span>');
  });
  it('retains manual mode and paths for existing profiles', () => {
    const server = {profile: {id: 'a', name: 'Server', host: 'example.org', username: 'u', port: 22,
      auth: 'password', key_path: '', python: '/env/bin/python', app_dir: '/code', workspace: '/work', mode: 'exec', menu_choice: ''},
      connected: false} as RemoteStatus;
    const html = renderToStaticMarkup(<RemotePanel {...props} servers={[server]}/>);
    expect(html).toContain('value="existing" selected');
    expect(html).toContain('/env/bin/python');
    expect(html).toContain('BioPipe 目录');
    expect(html).not.toContain('安装 / 升级服务端');
  });
  it('shows server version, catalog and readiness counts beside the connected refresh action', () => {
    const server = {profile: {id: 'a', name: 'Server', environment: 'managed'}, connected: true,
      info: {version: '0.7.1', system: 'linux', python: '/env/bin/python', catalog: {schema_version: 1, operators: []},
        dependencies: {running: false, entries: [{id: 'a', title: 'A', status: 'passed', error: ''}, {id: 'b', title: 'B', status: 'failed', error: 'missing'}]},
        tools: {samtools: true, bedtools: false}, history: [], workspace: '/work', automatic_memory_budget_bytes: 0, automatic_memory_fraction: 0.5} as RemoteInfo} as RemoteStatus;
    const html = renderToStaticMarkup(<RemotePanel {...props} servers={[server]}/>);
    expect(html).toContain('BioPipe 0.7.1');
    expect(html).toContain('算子 0');
    expect(html).toContain('依赖 1/2 已通过');
    expect(html).toContain('工具 1/2 可用');
    expect(html).toContain('刷新算子与依赖');
  });
  it('keeps older connected status usable without optional handshake or dependency data', () => {
    const server = {profile: {id: 'a', name: 'Server'}, connected: true,
      info: {version: '0.7.0', system: 'linux', catalog: {schema_version: 1, operators: []}, tools: {}} as unknown as RemoteInfo} as RemoteStatus;
    const html = renderToStaticMarkup(<RemotePanel {...props} servers={[server]}/>);
    expect(html).toContain('BioPipe 0.7.0');
    expect(html).toContain('刷新算子与依赖');
    expect(html).not.toContain('已通过');
  });
});
