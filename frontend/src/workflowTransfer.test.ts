import {afterEach, expect, it, vi} from 'vitest';
import {api} from './api';
import type {Graph} from './types';

afterEach(() => vi.unstubAllGlobals());

it('transfers the route bundle as binary and preserves concrete imported values', async () => {
  const graph = {schema_version: 2, name: 'Saved', nodes: [{id: 'pca', kind: 'operator', params: {n_components: 10}}], edges: []} as unknown as Graph;
  const bytes = new Uint8Array([80, 75, 3, 4, 0, 255, 129]);
  const fetcher = vi.fn()
    .mockResolvedValueOnce(Response.json({token: 'workflow-test-token'}))
    .mockResolvedValueOnce(new Response(bytes, {headers: {'Content-Type': 'application/zip'}}))
    .mockResolvedValueOnce(Response.json(graph));
  vi.stubGlobal('fetch', fetcher);
  await api.bootstrap();
  const bundle = await api.exportWorkflow(graph);
  expect(new Uint8Array(await bundle.arrayBuffer())).toEqual(bytes);
  const file = new File([bundle], 'saved.biopipe.zip', {type: 'application/zip'});
  expect(await api.importWorkflow(file)).toEqual(graph);
  expect(fetcher.mock.calls[1][1].headers['X-Studio-Token']).toBe('workflow-test-token');
  expect(fetcher.mock.calls[2][1].body).toBe(file);
  expect(fetcher.mock.calls[2][1].headers['Content-Type']).toBe('application/zip');
});

it('surfaces a broken pair error instead of opening a graph with new defaults', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(
    {message: 'Graph parameter values do not match the saved graph'}, {status: 422})));
  await expect(api.importWorkflow(new File(['broken'], 'bad.biopipe.zip')))
    .rejects.toThrow('Graph parameter values do not match the saved graph');
});
