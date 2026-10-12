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
    .mockImplementationOnce(() => pending as never);
  const receive = vi.fn((state:AgentState) => {workspace = state.workspace;});
  const bridge = new CanvasBridge(() => workspace, () => ({document_id:"a",nodes:[],edges:[],inspected_node:null,focused_field:""}), receive, vi.fn());
  const start = bridge.start();
  workspace.documents[0].graph.name = "Typed while connecting";
  resolve({id:"test",revision:0,ui_revision:0,seq:0,workspace:original,history:{},connections:{}});
  await start;
  expect(receive).not.toHaveBeenCalled();
  agent.mockResolvedValue({id:"test",revision:1,workspace});
  await bridge.flush();
  expect(agent).toHaveBeenLastCalledWith("/sessions/test/sync", expect.objectContaining({expected_revision:0,workspace}));
  expect(workspace.documents[0].graph.name).toBe("Typed while connecting");
});
