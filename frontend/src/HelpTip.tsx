import { useId, useState } from "react";
import type { ReactNode } from "react";
import { Info } from "@phosphor-icons/react";

/** Contextual help stays available to pointer, keyboard and touch users. */
export function HelpTip({ label, children, icon, above = false }: {
  label: string; children: ReactNode; icon?: ReactNode; above?: boolean;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  return <span className={`context-help ${above ? "above" : ""}`}
    onMouseEnter={() => setOpen(true)}
    onMouseLeave={event => {if (!event.currentTarget.contains(document.activeElement)) setOpen(false);}}
    onKeyDown={event => {if (event.key === "Escape") {setOpen(false); event.stopPropagation();}}}>
    <button type="button" className="icon-button" aria-label={label} aria-describedby={id}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
      onClick={event => {event.preventDefault(); event.stopPropagation(); setOpen(true);}}>
      {icon || <Info size={16}/>}
    </button>
    <span id={id} role="tooltip" className="context-help-content" hidden={!open}>{children}</span>
  </span>;
}
