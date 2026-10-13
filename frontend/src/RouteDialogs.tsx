import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ArrowRight, Check, FileArrowUp, Stack, X } from "@phosphor-icons/react";
import type { Catalog, ContractAnalysis, Graph, RouteOutput, SavedWorkflow, WorkflowSummary } from "./types";
import { api } from "./api";
import { clone, displayTitle, outputCount, specFor } from "./graph";
import { HelpTip } from "./HelpTip";

export function Modal({title, subtitle, onClose, children, dismissDisabled = false}: {title: string; subtitle?: string; onClose: () => void; children: ReactNode; dismissDisabled?: boolean}) {
  const box = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    (box.current?.querySelector<HTMLElement>('input:not(:disabled):not([hidden]):not([type="hidden"])') || box.current?.querySelector<HTMLElement>('button'))?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape" && event.target instanceof Element && event.target.closest(".context-help")?.querySelector('[role="tooltip"]:not([hidden])')) return;
      if (event.key === "Escape") {event.stopImmediatePropagation(); close.current();}
      if (event.key === "Tab") {
        const elements = [...(box.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select, textarea, [tabindex="0"]') || [])].filter(element => element.getClientRects().length > 0);
        const next = elements[(elements.indexOf(document.activeElement as HTMLElement) + (event.shiftKey ? -1 : 1) + elements.length) % elements.length];
        if (next) {event.preventDefault(); next.focus();}
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => {document.removeEventListener("keydown", handler, true); previous?.focus();};
  }, []);
  return <div className="modal-backdrop" onMouseDown={e => {if (e.target === e.currentTarget) onClose();}}>
    <div className="studio-modal" role="dialog" aria-modal="true" aria-label={title} ref={box}>
      <header><div className="modal-emblem"><Stack size={23}/></div><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" aria-label="关闭对话框" disabled={dismissDisabled} onClick={onClose}><X size={18}/></button></header>
      {children}
    </div>
  </div>;
}

export function WorkflowPicker({mode, onClose, onOpen, onRegister, onImport}: {
  mode: "open" | "register"; onClose: () => void; onOpen: (items: SavedWorkflow[]) => void;
  onRegister: () => Promise<void>; onImport: () => void;
}) {
  const [items, setItems] = useState<WorkflowSummary[]>([]), [selected, setSelected] = useState<string[]>([]);
  const [error, setError] = useState(""), [pending, setPending] = useState(true);
  useEffect(() => {let active = true; api.workflows().then(value => {if(active) setItems(value);}).catch(e => {if(active) setError(e.message);}).finally(() => {if(active) setPending(false);}); return () => {active = false;};}, []);
  async function accept() {
    setPending(true); setError("");
    try {
      if (mode === "register") {await api.registerRoutes(selected); await onRegister();}
      else onOpen(await Promise.all(selected.map(id => api.workflow(id))));
      onClose();
    } catch (e) {setError((e as Error).message);} finally {setPending(false);}
  }
  return <Modal title={mode === "register" ? "添加路线算子" : "打开已保存画布"} onClose={onClose}>
    <div className="workflow-picker-list">
      {!items.length && <div className="modal-empty"><Stack size={32} weight="light"/><p>{pending ? "正在读取保存的路线…" : "暂无已保存路线"}</p></div>}
      {items.map(item => <label className={`workflow-choice ${selected.includes(item.id) ? "checked" : ""}`} key={item.id}>
        <input type="checkbox" checked={selected.includes(item.id)} disabled={pending} onChange={e => setSelected(ids => e.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id))}/>
        <span className="workflow-choice-icon"><Stack size={20}/></span><span className="workflow-choice-text"><strong>{item.name}</strong><small>{item.nodes} 个节点 · {item.interface?.inputs.length || 0} 输入 / {item.interface?.outputs.length || 0} 输出 · v{item.version}</small></span>
        {item.registered_version && <span className="route-version">{item.registered_version === item.version ? "已注册" : `已注册 v${item.registered_version}`}</span>}
      </label>)}
    </div>
    {error && <p className="modal-error" role="alert">{error}</p>}
    <footer><button className="subtle-button" onClick={onImport} disabled={pending}><FileArrowUp size={16}/>导入路线文件</button><span className="modal-spacer"/><small>{selected.length ? `已选 ${selected.length} 条` : ""}</small><button className="primary-button" disabled={!selected.length || pending} onClick={() => void accept()}>{pending ? "处理中…" : mode === "register" ? "添加到算子库" : "打开画布"}<ArrowRight size={15}/></button></footer>
  </Modal>;
}

export function SaveWorkflowDialog({graph, catalog, workflowId, version, onClose, onSaved}: {
  graph: Graph; catalog: Catalog; workflowId?: string; version?: number; onClose: () => void; onSaved: (item: SavedWorkflow) => void;
}) {
  const [draft, setDraft] = useState<Graph>(clone(graph)), [analysis, setAnalysis] = useState<ContractAnalysis>();
  const [error, setError] = useState(""), [pending, setPending] = useState(true), [copy, setCopy] = useState(false);
  useEffect(() => {let active = true; Promise.all([api.prepareWorkflow(graph), api.contracts(graph)]).then(([prepared, ports]) => {if(active) {setDraft(prepared); setAnalysis(ports);}}).catch(e => {if(active) setError(e.message);}).finally(() => {if(active) setPending(false);}); return () => {active = false;};}, [graph]);
  const candidates: RouteOutput[] = draft.nodes.filter(n => n.kind !== "source").flatMap(node => {
    const spec = specFor(node, catalog), count = outputCount(node, spec);
    return Array.from({length: count}, (_, i) => ({node_id: node.id, handle: count === 1 ? "out" : `out-${i}`, label: node.route?.graph.interface?.outputs[i]?.label || displayTitle(node, spec), contract: analysis?.nodes[node.id]?.outputs[i] || {}}));
  });
  function setOutput(port: RouteOutput, enabled: boolean) {
    setDraft(value => ({...value, interface: {...value.interface!, outputs: enabled ? [...value.interface!.outputs, port] : value.interface!.outputs.filter(p => !(p.node_id === port.node_id && p.handle === port.handle))}}));
  }
  async function save() {
    setPending(true); setError("");
    try {onSaved(await api.saveWorkflow(draft, copy ? undefined : workflowId, copy ? undefined : version)); onClose();}
    catch(e) {setError((e as Error).message);} finally {setPending(false);}
  }
  return <Modal title="保存路线" onClose={onClose}>
    <div className="save-route-body">
      <label className="field"><span>路线名称</span><input autoFocus aria-label="路线名称" maxLength={120} value={draft.name} onChange={e => setDraft({...draft, name: e.target.value})}/></label>
      <div className="route-interface-grid">
        <section><h3>输入接口 <small>{draft.interface?.inputs.length || 0}</small><HelpTip label="输入接口说明">调用路线时，外部连线替代内部数据源。</HelpTip></h3>
          {draft.interface?.inputs.map((port, i) => <label className="interface-port" key={port.node_id}><span className="port-number">{i+1}</span><input aria-label={`输入接口 ${i+1}`} value={port.label} maxLength={120} onChange={e => setDraft({...draft, interface: {...draft.interface!, inputs: draft.interface!.inputs.map((p,j) => i===j ? {...p,label:e.target.value} : p)}})}/></label>)}
          {!draft.interface?.inputs.length && <small className="muted">暂无输入数据</small>}
        </section>
        <section><h3>输出接口 <small>{draft.interface?.outputs.length || 0}</small><HelpTip label="输出接口说明">勾选需要向外传递的数据，勾选顺序即端口顺序。</HelpTip></h3>
          {candidates.map(port => {const selected = draft.interface?.outputs.find(p => p.node_id === port.node_id && p.handle === port.handle); return <label className="interface-port" key={`${port.node_id}-${port.handle}`}>
            <input type="checkbox" checked={!!selected} onChange={e => setOutput(port, e.target.checked)}/><input aria-label={`输出接口 ${port.label}`} value={selected?.label || port.label} maxLength={120} disabled={!selected} onChange={e => setDraft({...draft, interface: {...draft.interface!, outputs: draft.interface!.outputs.map(p => p === selected ? {...p, label: e.target.value} : p)}})}/>
          </label>;})}
          {!candidates.length && <small className="muted">无数据输出</small>}
        </section>
      </div>
      {workflowId && <label className="check-field"><input type="checkbox" checked={copy} onChange={e => setCopy(e.target.checked)}/><span>另存为新路线<small>当前版本 v{version}，已有算子实例保持原版本。</small></span></label>}
    </div>
    {error && <p className="modal-error" role="alert">{error}</p>}
    <footer><span className="modal-spacer"/><button className="subtle-button" onClick={onClose}>取消</button><button className="primary-button" disabled={pending || !draft.interface || !draft.name.trim() || draft.interface.inputs.some(p=>!p.label.trim()) || draft.interface.outputs.some(p=>!p.label.trim())} onClick={() => void save()}><Check size={16}/>{pending ? "处理中…" : "保存路线"}</button></footer>
  </Modal>;
}
