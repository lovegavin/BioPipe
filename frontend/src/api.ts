import type { Bootstrap, Graph, Job, Preview, ContractAnalysis, Workspace, SavedWorkflow, WorkflowSummary, RouteDefinition, DataSource } from "./types";
import type { LibraryState, LibraryAction } from "./types";

const base =
  (import.meta as ImportMeta & { env: { VITE_API_BASE?: string } }).env
    .VITE_API_BASE || "";
let token = "";
let workspaceWrite: Promise<unknown> = Promise.resolve();
export class ApiError extends Error {
  constructor(
    message: string,
    public nodeId?: string,
    public status?: number,
    public code?: string,
  ) {
    super(message);
  }
}
async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(base + path, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      ...(token ? { "X-Studio-Token": token } : {}),
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let value;
  try {
    value = await response.json();
  } catch {
    throw new ApiError("本地服务未返回有效响应，请确认服务已启动。");
  }
  if (!response.ok) {
    const details = Array.isArray(value.detail)
      ? value.detail.map((d: { msg: string }) => d.msg).join("；")
      : value.detail;
    throw new ApiError(
      value.message || details || "操作未完成，请重试。",
      value.node_id,
      response.status,
      value.code,
    );
  }
  return value as T;
}
export const api = {
  plugins: () => request<import('./types').PluginState>('/api/plugins'),
  refreshPlugins: () => request<import('./types').PluginOperation>('/api/plugins/refresh', {}),
  repairDependencies: () => request<import('./types').PluginOperation>('/api/plugins/dependencies', {}),
  openPluginFolder: (kind: 'operator' | 'reader' | 'extra' = 'operator') => request<{directory: string}>('/api/plugins/open-folder', {kind}),
  pluginOperation: (id: string) => request<import('./types').PluginOperation>(`/api/plugins/operations/${encodeURIComponent(id)}`),
  removePlugin: (name: string) => request<import('./types').PluginOperation>('/api/plugins/remove', {name}),
  managePlugin: (name: string, action: 'enable' | 'disable' | 'restore') => request<import('./types').PluginOperation>('/api/plugins/manage', {name, action}),
  installPlugin: async (file: File): Promise<import('./types').PluginOperation> => {
    const response = await fetch(base + '/api/plugins/install?filename=' + encodeURIComponent(file.name), {
      method: 'POST', headers: {'X-Studio-Token': token, 'Content-Type': 'application/octet-stream'}, body: file,
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.message || result.detail || '插件安装未完成');
    return result;
  },
  agent: <T,>(path: string, body?: unknown) => request<T>("/api/agent" + path, body),
  catalog: () => request<Bootstrap["catalog"]>("/api/operators"),
  workspace: () => request<Workspace | null>("/api/workspace"),
  saveWorkspace: (workspace: Workspace) => {
    workspaceWrite = workspaceWrite.catch(() => undefined).then(() => request<{saved: boolean}>("/api/workspace", workspace));
    return workspaceWrite;
  },
  workflows: () => request<WorkflowSummary[]>("/api/workflows"),
  workflow: (id: string) => request<SavedWorkflow>(`/api/workflows/${encodeURIComponent(id)}`),
  prepareWorkflow: (graph: Graph) => request<Graph>("/api/workflows/prepare", graph),
  saveWorkflow: (graph: Graph, id?: string, expected_version?: number) => request<SavedWorkflow>("/api/workflows/save", {graph, id, expected_version}),
  routes: () => request<RouteDefinition[]>("/api/routes"),
  libraryState: () => request<LibraryState>("/api/library/state"),
  manageLibrary: (key: string, action: LibraryAction) => request<{routes: RouteDefinition[]; state: LibraryState}>("/api/library/manage", {key, action}),
  registerRoutes: (workflow_ids: string[]) => request<RouteDefinition[]>("/api/routes/register", {workflow_ids}),
  bootstrap: async () => {
    const data = await request<Bootstrap>("/api/bootstrap");
    token = data.token;
    return data;
  },
  validate: (graph: Graph) =>
    request<{ valid: boolean; order: string[]; contracts: ContractAnalysis }>("/api/validate", graph),
  contracts: (graph: Graph) => request<ContractAnalysis>("/api/contracts", graph),
  export: (graph: Graph) =>
    request<{ yaml: string; order: string[] }>("/api/export", graph),
  import: (text: string, base_dir: string) =>
    request<Graph>("/api/import", { text, base_dir }),
  run: (graph: Graph) => request<Job>("/api/jobs", graph),
  history: () => request<Job[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${encodeURIComponent(id)}`),
  cancel: (id: string) =>
    request<Job>(`/api/jobs/${encodeURIComponent(id)}/cancel`, {}),
  preview: (id: string, artifact: string) =>
    request<Preview>(
      `/api/jobs/${encodeURIComponent(id)}/artifacts/${encodeURIComponent(artifact)}/preview`,
    ),
  step: (id: string, index: number) =>
    request<Record<string, unknown>>(
      `/api/jobs/${encodeURIComponent(id)}/exports/${index}`,
    ),
  url: (path: string) => base + path,
  uploadFiles: async (files: File[], base_dir: string) => {
    const batch = await request<{ id: string }>("/api/assets/batches", {filenames: files.map(file => file.name)});
    try {
      for (const file of files) await api.upload(file, batch.id);
      return await request<{source: DataSource; filename: string; reader: string; files: string[]}>(
        `/api/assets/batches/${batch.id}/complete`, {base_dir});
    } catch (error) {
      await request(`/api/assets/batches/${batch.id}/cancel`, {}).catch(() => undefined);
      throw error;
    }
  },
  upload: async (file: File, batch?: string) => {
    const response = await fetch(
      `${base}/api/assets?filename=${encodeURIComponent(file.name)}${batch ? `&batch=${encodeURIComponent(batch)}` : ''}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Studio-Token": token,
        },
        body: file,
      },
    );
    const value = await response.json();
    if (!response.ok)
      throw new ApiError(value.message || value.detail || "上传失败。");
    return value as { path: string; filename: string; bytes: number };
  },
};
export function downloadText(
  name: string,
  text: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
