import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it} from 'vitest';
import {RemotePanel} from './RemotePanel';
import type {RemoteStatus} from './types';

const props = {active: '', onUpdate: async () => {}, onSelect: () => {}, onClose: () => {}};
describe('server environment setup', () => {
  it('defaults new connections to automatic deployment without mandatory server Python paths', () => {
    const html = renderToStaticMarkup(<RemotePanel {...props} servers={[]}/>);
    expect(html).toContain('value="managed" selected');
    expect(html).toContain('安装目录');
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
  });
});
