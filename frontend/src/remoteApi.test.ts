import {afterEach, describe, expect, it, vi} from 'vitest';
import {api} from './api';

afterEach(() => vi.unstubAllGlobals());
describe('remote API actions', () => {
  it.each([
    ['connect', () => api.connectRemote('server-a', {password: 'session-only'}), {password: 'session-only'}],
    ['install', () => api.installRemote('server-a', {passphrase: 'session-only'}), {passphrase: 'session-only'}],
    ['refresh', () => api.refreshRemote('server-a'), {}],
  ] as const)('posts %s only to its dedicated endpoint', async (action, request, body) => {
    const response = {version: '0.7.1'};
    const fetch = vi.fn().mockResolvedValue({ok: true, json: async () => response});
    vi.stubGlobal('fetch', fetch);
    expect(await request()).toEqual(response);
    expect(fetch).toHaveBeenCalledExactlyOnceWith(`/api/remote/server-a/${action}`, expect.objectContaining({method: 'POST', body: JSON.stringify(body)}));
  });
  it('preserves the server error code for actionable UI', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: false, status: 409, json: async () => ({code: 'server_not_installed', message: 'Install first'})}));
    await expect(api.connectRemote('server-a', {})).rejects.toMatchObject({code: 'server_not_installed', message: 'Install first', status: 409});
  });
  it.each(['server_incompatible', 'handshake_incompatible', 'capability_missing', 'handshake_required'])('preserves actionable server guidance for %s', async code => {
    const message = '服务端仍有任务运行，请等待任务结束，再升级并重启服务端。';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: false, status: 409, json: async () => ({code, message})}));
    await expect(api.connectRemote('server-a', {})).rejects.toMatchObject({code, message, status: 409});
  });
});
