import {afterEach, expect, it, vi} from 'vitest';
import {api} from './api';
import {setLanguage} from './i18n';

afterEach(() => {vi.unstubAllGlobals(); setLanguage('system');});

it.each([['zh-CN', '文件不存在'], ['en', 'File not found']] as const)(
  'shows the missing sidecar and retry directory in %s', async (language, reason) => {
    setLanguage(language);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: false, status: 422, json: async () => ({
      code: 'workflow_resource_error', message: 'not a generic service error',
      details: {reason: 'missing', resource: 'parameters.json', directory: '/workspace/project'},
    })}));
    await expect(api.import('format: operon.workflow', '.')).rejects.toMatchObject({
      code: 'workflow_resource_error', status: 422,
      message: expect.stringContaining(reason),
    });
    await expect(api.import('format: operon.workflow', '.')).rejects.toThrow('parameters.json');
    await expect(api.import('format: operon.workflow', '.')).rejects.toThrow('/workspace/project');
  });
