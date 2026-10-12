import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { Info } from "@phosphor-icons/react";
import { contractRows } from "./contracts";
import type { ContractCheck, PortContract } from "./types";

const NO_CHECKS: ContractCheck[] = [];

export function InfoPort({ direction, height, ports, checks = NO_CHECKS, hint, children, source = false, labels }: {
  direction: "input" | "output";
  height: number;
  ports?: (PortContract | null)[];
  checks?: ContractCheck[];
  hint: ReactNode;
  children?: ReactNode;
  source?: boolean;
  labels?: string[];
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const anchor = useRef<HTMLDivElement>(null), panel = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const id = useId();
  const title = direction === "input" ? source ? "文件 info" : "输入 info" : "输出 info";
  function show() { clearTimeout(timer.current); setOpen(true); }
  function hide() { clearTimeout(timer.current); timer.current = setTimeout(() => setOpen(false), 130); }
  useEffect(() => () => clearTimeout(timer.current), []);
  useLayoutEffect(() => {
    if (!open || !anchor.current || !panel.current) return;
    const rect = anchor.current.getBoundingClientRect(), width = panel.current.offsetWidth, height = panel.current.offsetHeight;
    const left = rect.right + width + 16 < window.innerWidth ? rect.right + 12 : Math.max(12, rect.left - width - 12);
    const top = Math.max(12, Math.min(rect.top - 8, window.innerHeight - height - 12));
    setPosition(previous => previous.left === left && previous.top === top ? previous : { left, top });
  }, [open, ports, checks]);
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    const dismiss = () => setOpen(false);
    window.addEventListener("keydown", close);
    window.addEventListener("resize", dismiss);
    return () => { window.removeEventListener("keydown", close); window.removeEventListener("resize", dismiss); };
  }, [open]);
  const incompatible = checks.some(check => check.status === "incompatible");
  const uncertain = checks.some(check => check.status === "unknown");
  const status = incompatible ? "不兼容" : uncertain ? "运行时确认" : checks.length ? "契约兼容" : "端口契约";
  return <div ref={anchor} className={`node-port-row ${direction}-row`} style={{ height }}
    onMouseEnter={show} onMouseLeave={hide} onPointerDown={event => { if (!(event.target as HTMLElement).closest("button")) setOpen(false); }}>
    <button className="port-info-trigger nodrag" aria-label={title} aria-describedby={open ? id : undefined}
      onFocus={show} onBlur={hide} onClick={event => { event.stopPropagation(); setOpen(value => !value); }}
      onDoubleClick={event => event.stopPropagation()}>
      <Info size={12} /><span>{title}</span>
      {incompatible && <i className="contract-dot error" />}
      {!incompatible && uncertain && <i className="contract-dot pending" />}
    </button>
    <span className="port-side">{hint}</span>
    {children}
    {open && createPortal(<div ref={panel} id={id} role="tooltip" className="info-popover nodrag nowheel" style={position}
      onMouseEnter={show} onMouseLeave={hide}>
      <header><span><Info size={15} />{title}</span><small className={incompatible ? "error-text" : ""}>{status}</small></header>
      <div className="info-popover-content">
        {ports === undefined ? <p>正在分析契约…</p> : ports.length === 0 ? <p>{source ? "Reader 根据文件格式输出数据与 info；连线前不加载文件内容。" : "此算子生成报告或图表，没有数据输出端口。"}</p> : ports.map((port, index) =>
          <section key={index}>
            {(ports.length > 1 || labels?.[index]) && <h4>{direction === "input" ? "输入" : "输出"} {index + 1}{labels?.[index] ? ` · ${labels[index]}` : ""}</h4>}
            <dl>{contractRows(port).map(([field, value], index) => <div key={`${field}-${index}`}><dt>{field}</dt><dd>{value}</dd></div>)}</dl>
          </section>)}
        {checks.filter(check => check.status !== "compatible").map(check => <p className={`contract-note ${check.status}`} key={check.id}>{check.reasons.join("；")}</p>)}
      </div>
      <footer>结构与字段预检 · 实际数值在运行时校验</footer>
    </div>, document.body)}
  </div>;
}
