import {renderToStaticMarkup} from 'react-dom/server';
import {describe, expect, it, vi} from 'vitest';
import {SettingsPage} from './SettingsPage';
import {RemotePanel} from './RemotePanel';
import {AppearanceSettings} from './AppearanceSettings';

describe('central settings', () => {
  it('hosts server controls without nested dialogs and keeps section contents mounted', () => {
    const html = renderToStaticMarkup(<SettingsPage initial="viewers" servers={[]} active="" onClose={() => {}} onSelect={() => {}} onUpdate={async () => {}} appearance={{preference:'system',onChange:()=>{}}}/>);
    expect(html.match(/role="dialog"/g)).toHaveLength(1);
    expect(html).toContain('aria-current="page"><svg');
    expect(html).toContain('服务器连接');
    expect(html).toContain('默认打开方式');
    expect(html).toContain('aria-label="关闭设置"');
    expect(html).not.toContain('关闭服务器面板');
  });
  it('retains standalone server dialog for existing callers', () => {
    const html = renderToStaticMarkup(<RemotePanel servers={[]} active="" onClose={()=>{}} onSelect={()=>{}} onUpdate={async()=>{}}/>);
    expect(html).toContain('role="dialog"'); expect(html).toContain('关闭服务器面板');
  });
  it('shows the existing theme preference with native radio controls', () => {
    const html = renderToStaticMarkup(<AppearanceSettings preference="dark" onChange={vi.fn()}/>);
    expect(html).toMatch(/type="radio"[^>]*checked=""[^>]*value="dark"/);
    expect(html).toContain('跟随系统');
  });
});
