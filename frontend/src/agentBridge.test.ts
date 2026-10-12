import { describe, expect, it } from "vitest";
import { recoverWorkspace } from "./agentBridge";
import type { Workspace } from "./types";

const base: Workspace = {schema_version: 1, active_id: "a", documents: [{id: "a", graph: {
  schema_version: 2, name: "Original", base_dir: ".", nodes: [], edges: [], memory: {enabled: true},
}}]};

describe("concurrent canvas edits", () => {
  it("preserves an agent edit and local conflicting work in independent tabs", () => {
    const local = structuredClone(base), remote = structuredClone(base);
    local.documents[0].graph.name = "User edit";
    remote.documents[0].graph.name = "Agent edit";
    const result = recoverWorkspace(base, local, remote);
    expect(result.documents).toHaveLength(2);
    expect(result.documents[0].graph.name).toBe("Agent edit");
    expect(result.documents[1].graph.name).toContain("User edit");
    expect(result.documents[1].id).not.toBe("a");
    expect(base.documents[0].graph.name).toBe("Original");
  });
  it("merges local changes when the remote document has not changed", () => {
    const local = structuredClone(base);
    local.documents[0].graph.name = "New name";
    expect(recoverWorkspace(base, local, base).documents[0].graph.name).toBe("New name");
  });
  it("does not duplicate an already applied edit", () => {
    const edited = structuredClone(base);
    edited.documents[0].graph.name = "Changed";
    expect(recoverWorkspace(base, edited, edited).documents).toHaveLength(1);
  });
});
