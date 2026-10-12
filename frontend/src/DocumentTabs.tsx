import { Plus, X, Stack, File } from "@phosphor-icons/react";
import { useState } from "react";
import type { WorkspaceDocument } from "./types";

export function DocumentTabs({documents, active, saved, onSelect, onClose, onNew, onRename}: {
  documents: WorkspaceDocument[]; active: string; saved: boolean;
  onSelect: (id: string) => void; onClose: (id: string) => void; onNew: () => void; onRename: (name: string) => void;
}) {
  const [renaming, setRenaming] = useState<string | null>(null);
  return <div className="document-strip">
    <div className="document-tabs" role="tablist" aria-label="打开的画布">
      {documents.map((doc, index) => <div className={`document-tab ${doc.id === active ? "is-active" : ""}`} key={doc.id}>
        <button role="tab" aria-selected={doc.id === active} aria-controls="workflow-canvas" tabIndex={doc.id === active ? 0 : -1}
          title={`${doc.graph.name}${doc.workflow_version ? ` · v${doc.workflow_version}` : ""} · 双击重命名`}
          onClick={() => onSelect(doc.id)} onDoubleClick={() => {onSelect(doc.id); setRenaming(doc.id);}}
          onKeyDown={event => {
            if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
              event.preventDefault(); const i = event.key === "Home" ? 0 : event.key === "End" ? documents.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + documents.length) % documents.length;
              onSelect(documents[i].id);
              (event.currentTarget.closest('[role="tablist"]')?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[i])?.focus();
            }
            if (event.key === "F2") {event.preventDefault(); setRenaming(doc.id);}
          }}>
          {doc.workflow_id ? <Stack size={15}/> : <File size={15}/>}
          <span>{doc.graph.name}</span>
          {doc.id === active && !saved && <i className="document-dirty" aria-label="正在保存草稿"/>}
        </button>
        {renaming === doc.id && <input className="document-rename" aria-label="工作流名称" autoFocus maxLength={120} defaultValue={doc.graph.name}
          onBlur={e => {onRename(e.target.value.trim() || doc.graph.name); setRenaming(null);}}
          onKeyDown={e => {if (e.key === "Enter") e.currentTarget.blur(); if (e.key === "Escape") {e.currentTarget.value = doc.graph.name; e.currentTarget.blur();}}}/>}
        <button className="document-close" aria-label={`关闭 ${doc.graph.name}`} title="关闭页面（草稿可恢复）" onClick={() => onClose(doc.id)}><X size={12}/></button>
      </div>)}
    </div>
    <button className="icon-button new-document" aria-label="新建画布" title="新建画布" onClick={onNew}><Plus size={17}/></button>
  </div>;
}
