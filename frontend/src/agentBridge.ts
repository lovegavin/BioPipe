import { api, ApiError } from "./api";
import type { Workspace } from "./types";

export type AgentState = {
  id: string; revision: number; ui_revision: number; seq: number;
  workspace: Workspace;
  connections: Record<string, string>;
  history: Record<string, {undo: number; redo: number}>;
};
export type Presence = {document_id: string; nodes: string[]; edges: string[]; inspected_node: string | null; focused_field: string; viewport?: unknown};
export const signature = (value: unknown): string => JSON.stringify(value, (_key, item) =>
  item && typeof item === "object" && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().filter(key => item[key] !== undefined).map(key => [key, item[key]])) : item);

/** Keep conflicting local work in a separate tab, never overwrite agent edits. */
export function recoverWorkspace(base: Workspace, local: Workspace, remote: Workspace): Workspace {
  const result = structuredClone(remote);
  for (const doc of local.documents) {
    const before = base.documents.find(item => item.id === doc.id);
    if (before && signature(before.graph) === signature(doc.graph)) continue;
    const target = result.documents.find(item => item.id === doc.id);
    if (!target) result.documents.push(structuredClone(doc));
    else if (before && signature(target.graph) === signature(before.graph)) target.graph = structuredClone(doc.graph);
    else if (signature(target.graph) !== signature(doc.graph)) {
      result.documents.push({...structuredClone(doc), id: `page_${crypto.randomUUID()}`,
        workflow_id: undefined, workflow_version: undefined,
        graph: {...structuredClone(doc.graph), name: `${doc.graph.name} · Recovered edits`}});
    }
  }
  if (result.documents.length > 20) throw Error("恢复的编辑超过 20 个标签页。请先导出当前画布，再重新连接。");
  return result;
}

export class CanvasBridge {
  state: AgentState | null = null;
  private acknowledged: Workspace | null = null;
  private queue: Promise<unknown> = Promise.resolve();
  private stopped = false;
  constructor(private capture: () => Workspace, private presence: () => Presence,
              private receive: (value: AgentState) => void, private notify: (message: string) => void) {}

  async start() {
    const workspace = structuredClone(this.capture());
    const state = await api.agent<AgentState>("/sessions", {workspace, name: workspace.documents.find(d => d.id === workspace.active_id)?.graph.name || "BioPipe Studio"});
    if (this.stopped) return;
    this.state = state;
    this.acknowledged = workspace;
    if (signature(workspace) === signature(this.capture())) {
      this.receive(state);
      this.acknowledged = structuredClone(this.capture());
    }
    await this.publishPresence();
  }

  private serialized<T>(work: () => Promise<T>): Promise<T> {
    const pending = this.queue.catch(() => undefined).then(work);
    this.queue = pending;
    return pending;
  }

  private async publishPresence() {
    if (this.state) await api.agent(`/sessions/${this.state.id}/presence`, this.presence());
  }

  private async flushNow() {
    if (!this.state || !this.acknowledged || this.stopped) return;
    const workspace = structuredClone(this.capture());
    if (signature(workspace) === signature(this.acknowledged)) return;
    try {
      const state = await api.agent<AgentState>(`/sessions/${this.state.id}/sync`, {workspace, expected_revision: this.state.revision});
      this.state = state;
      this.acknowledged = workspace;
      // No receive(): a newer keystroke may already be visible while this
      // request was in flight. It is flushed by the next iteration.
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 409) throw error;
      const remote = await api.agent<AgentState>(`/sessions/${this.state.id}`);
      const local = structuredClone(this.capture());
      // Preserve a recoverable local copy even if tab capacity prevents merge.
      localStorage.setItem("biopipe-agent-conflict-backup", JSON.stringify(local));
      const recovered = recoverWorkspace(this.acknowledged, local, remote.workspace);
      const state = await api.agent<AgentState>(`/sessions/${remote.id}/sync`, {workspace: recovered, expected_revision: remote.revision});
      this.state = state;
      const latest = structuredClone(this.capture());
      if (signature(latest) === signature(local)) {
        this.receive(state);
        this.acknowledged = structuredClone(this.capture());
      } else {
        // Edits made while recovery was in flight remain visible and are
        // merged against the acknowledged recovery on the next flush.
        const merged = recoverWorkspace(local, latest, state.workspace);
        this.receive({...state, workspace: merged});
        this.acknowledged = structuredClone(state.workspace);
      }
      this.notify("画布同时发生修改，冲突的本地编辑已保留在恢复标签页中。");
    }
  }

  flush() {return this.serialized(() => this.flushNow());}

  tick() {
    return this.serialized(async () => {
      if (!this.state || this.stopped) return;
      await this.flushNow();
      const captured = signature(this.capture());
      const remote = await api.agent<AgentState>(`/sessions/${this.state.id}`);
      if (remote.revision !== this.state.revision) {
        // Let flushNow resolve a concurrent local edit before replacing UI.
        if (captured !== signature(this.capture())) return;
        this.state = remote;
        this.receive(remote);
        this.acknowledged = structuredClone(this.capture());
      }
      await this.publishPresence();
    });
  }

  undo(document: string, redo = false) {
    return this.serialized(async () => {
      await this.flushNow();
      if (!this.state) return;
      const state = await api.agent<AgentState>(`/sessions/${this.state.id}/undo`, {
        document_id: document, expected_revision: this.state.revision, redo,
      });
      this.state = state;
      this.receive(state);
      this.acknowledged = structuredClone(this.capture());
    });
  }

  context() {
    return this.serialized(async () => {
      await this.flushNow();
      await this.publishPresence();
      if (!this.state) throw Error("Agent 接口尚未就绪");
      return api.agent(`/sessions/${this.state.id}/context?scope=selection`);
    });
  }
  stop() {this.stopped = true;}
}
