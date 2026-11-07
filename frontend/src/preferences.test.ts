import {afterEach, describe, expect, it, vi} from 'vitest';

afterEach(() => {vi.unstubAllGlobals(); vi.resetModules();});
describe('shared application preferences', () => {
  it('imports browser-only choices and then caches one configuration object', async () => {
    const values = new Map([['operon-studio-theme-v1', 'dark'], ['operon-studio-language-v1', 'en']]);
    vi.stubGlobal('localStorage', {getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value)});
    const prefs = await import('./preferences');
    expect(prefs.getPreferences()).toEqual({language: 'en', theme: 'dark'});
    prefs.setPreferences({language: 'zh-CN'});
    expect(JSON.parse(values.get('operon-studio-config-v1')!)).toEqual({language: 'zh-CN', theme: 'dark'});
    vi.resetModules();
    expect((await import('./preferences')).getPreferences()).toEqual({language: 'zh-CN', theme: 'dark'});
  });
  it('serializes updates so a slow theme response cannot undo a newer language choice', async () => {
    const finish: ((value: unknown) => void)[] = [];
    const fetch = vi.fn(() => new Promise(resolve => finish.push(resolve)));
    vi.stubGlobal('fetch', fetch);
    const {api} = await import('./api');
    const theme = api.savePreferences({theme: 'dark'});
    const language = api.savePreferences({language: 'en'});
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    finish[0]({ok: true, json: async () => ({language: 'system', theme: 'dark'})});
    await theme;
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    finish[1]({ok: true, json: async () => ({language: 'en', theme: 'dark'})});
    expect(await language).toEqual({language: 'en', theme: 'dark'});
  });
});
