import type { Bootstrap, Graph, Job, Preview, ContractAnalysis, Workspace, SavedWorkflow, WorkflowSummary, RouteDefinition } from "./types";
import type { LibraryState, LibraryAction } from "./types";

const base =
  (import.meta as ImportMeta & { env: { VITE_API_BASE?: string } }).env
    .VITE_API_BASE || "";
let token = "";
let draftWrite: Promise<unknown> = Promise.resolve();
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
  agent: <T,>(path: string, body?: unknown) => request<T>("/api/agent" + path, body),
  catalog: () => request<Bootstrap["catalog"]>("/api/operators"),
  workspace: () => request<Workspace | null>("/api/workspace"),
  saveWorkspace: (workspace: Workspace) => {
    draftWrite = draftWrite.catch(() => undefined).then(() => request<{saved: boolean}>("/api/workspace", workspace));
    return draftWrite;
  },
  workflows: () => request<WorkflowSummary[]>("/api/workflows"),
  workflow: (id: string) => request<SavedWorkflow>(`/api/workflows/${encodeURIComponent(id)}`),
  prepareWorkflow: (graph: Graph) => request<Graph>("/api/workflows/prepare", graph),
  saveWorkflow: (graph: Graph, id?: string, expected_version?: number) => request<SavedWorkflow>("/api/workflows/save", {graph, id, expected_version}),
  routes: () => request<RouteDefinition[]>("/api/routes"),
  libraryState: () => request<LibraryState>("/api/library/state"),
  manageLibrary: (key: string, action: LibraryAction) => request<{routes: RouteDefinition[]; state: LibraryState}>("/api/library/manage", {key, action}),
  registerRoutes: (workflow_ids: string[]) => request<RouteDefinition[]>("/api/routes/register", {workflow_ids}),
  saveDraft: (graph: Graph) => {
    // Serialize writes so an earlier autosave cannot overwrite a newer draft.
    draftWrite = draftWrite
      .catch(() => undefined)
      .then(() => request<{ saved: boolean }>("/api/draft", graph));
    return draftWrite;
  },
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
  upload: async (file: File) => {
    const response = await fetch(
      `${base}/api/assets?filename=${encodeURIComponent(file.name)}`,
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
