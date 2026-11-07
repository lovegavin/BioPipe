import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
import { CanvasBridge, type AgentState } from "./agentBridge";
import type { Workspace } from "./types";

afterEach(() => {vi.restoreAllMocks(); vi.unstubAllGlobals();});

it("authenticates read requests as well as canvas writes", async () => {
  const fetch = vi.fn()
    .mockResolvedValueOnce({ok:true, json:async () => ({token:"test-token"})})
    .mockResolvedValueOnce({ok:true, json:async () => ({revision:0})});
  vi.stubGlobal("fetch", fetch);
  await api.bootstrap();
  await api.agent("/sessions/test");
  expect(fetch.mock.calls[1][1].headers["X-Studio-Token"]).toBe("test-token");
});

it("keeps a user edit made while the session is connecting", async () => {
  let workspace: Workspace = {schema_version:1, active_id:"a", documents:[{id:"a", graph:{
    schema_version:2, name:"Before", base_dir:".", nodes:[], edges:[], memory:{enabled:true},
  }}]};
  const original = structuredClone(workspace);
  let resolve!: (state: AgentState) => void;
  const pending = new Promise<AgentState>(done => {resolve = done;});
  const agent = vi.spyOn(api,"agent").mockResolvedValue({})
    .mockResolvedValueOnce([])
    .mockImplementationOnce(() => pending as never);
  const receive = vi.fn((state:AgentState) => {workspace = state.workspace;});
  const bridge = new CanvasBridge(() => workspace, () => ({document_id:"a",nodes:[],edges:[],inspected_node:null,focused_field:""}), receive, vi.fn());
  const start = bridge.start();
  await Promise.resolve();
  workspace.documents[0].graph.name = "Typed while connecting";
  resolve({id:"test",revision:0,ui_revision:0,seq:0,workspace:original,history:{},connections:{}});
  await start;
  expect(receive).not.toHaveBeenCalled();
  agent.mockResolvedValue({id:"test",revision:1,workspace});
  await bridge.flush();
  expect(agent).toHaveBeenLastCalledWith("/sessions/test/sync", expect.objectContaining({expected_revision:0,workspace}));
  expect(workspace.documents[0].graph.name).toBe("Typed while connecting");
});

it('restores a durable session and polls compact events before fetching a changed graph', async () => {
  let workspace: Workspace = {schema_version:1, active_id:'a', documents:[{id:'a', graph:{
    schema_version:2, name:'Old', base_dir:'.', nodes:[], edges:[], memory:{enabled:true},
  }}]};
  const saved = {...structuredClone(workspace), documents:workspace.documents.map(doc => ({...doc,graph:{...doc.graph,name:'Headless edit'}}))};
  const state: AgentState = {id:'persisted',revision:4,ui_revision:0,seq:4,workspace:saved,history:{},connections:{}};
  const receive = vi.fn((next:AgentState) => {workspace = next.workspace;});
  const activity = vi.fn();
  const agent = vi.spyOn(api,'agent').mockImplementation(async (path: string) => {
    if(path === '/sessions') return [{...state,document_ids:['a'],updated_at:'2026-11-06'}] as never;
    if(path === '/sessions/persisted') return state as never;
    if(path.includes('/events?')) return {seq:4,next_cursor:4,revision:4,reset:false,has_more:false,events:[]} as never;
    return {} as never;
  });
  const bridge = new CanvasBridge(() => workspace, () => ({document_id:'a',nodes:[],edges:[],inspected_node:null,focused_field:''}),receive,vi.fn(),activity);
  await bridge.start();
  expect(workspace.documents[0].graph.name).toBe('Headless edit');
  await bridge.tick();
  expect(agent.mock.calls.filter(([path]) => path === '/sessions/persisted')).toHaveLength(1);
  expect(agent.mock.calls.some(([path]) => path.includes('/events?after=0&limit=50'))).toBe(true);
  expect(activity).toHaveBeenCalledWith([],false);
  expect(agent.mock.calls.some(([path,body]) => path === '/sessions' && body)).toBe(false);
});

it.each(['connect', 'poll'] as const)('syncs a newly opened tab before publishing its presence during %s', async phase => {
  let workspace: Workspace = {schema_version:1, active_id:'a', documents:[{id:'a', graph:{
    schema_version:2, name:'Original', base_dir:'.', nodes:[], edges:[], memory:{enabled:true},
  }}]};
  let state: AgentState = {id:'test',revision:0,ui_revision:0,seq:0,workspace:structuredClone(workspace),history:{},connections:{}};
  const openTab = () => {
    workspace = {...workspace, active_id:'b', documents:[...workspace.documents,
      {id:'b', graph:{...structuredClone(workspace.documents[0].graph),name:'New canvas'}}]};
  };
  const published: string[] = [];
  let opened = false;
  vi.spyOn(api,'agent').mockImplementation(async (path, body) => {
    if(path === '/sessions' && !body) return [] as never;
    if(path === '/sessions') {
      if(phase === 'connect') openTab();
      return structuredClone(state) as never;
    }
    if(path.endsWith('/sync')) {
      state = {...state,revision:state.revision+1,workspace:structuredClone((body as {workspace:Workspace}).workspace)};
      return structuredClone(state) as never;
    }
    if(path.includes('/events?')) {
      if(phase === 'poll' && !opened) {openTab(); opened = true;}
      return {revision:state.revision,next_cursor:0,events:[],reset:false} as never;
    }
    if(path.endsWith('/presence')) {
      const documentId = (body as {document_id:string}).document_id;
      if(!state.workspace.documents.some(doc => doc.id === documentId))
        throw Error('Presence references an unknown document');
      published.push(documentId);
    }
    return {} as never;
  });
  const bridge = new CanvasBridge(() => workspace, () => ({document_id:workspace.active_id,
    nodes:[],edges:[],inspected_node:null,focused_field:''}), value => {workspace = value.workspace;}, vi.fn());
  await bridge.start();
  await bridge.tick();
  await bridge.tick();
  expect(workspace.active_id).toBe('b');
  expect(state.workspace.documents.map(doc => doc.id)).toEqual(['a','b']);
  expect(published.at(-1)).toBe('b');
});
