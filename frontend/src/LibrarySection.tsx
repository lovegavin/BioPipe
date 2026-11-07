import { useEffect, useId, useState } from "react";
import type { ReactNode } from "react";
import { CaretDown } from "@phosphor-icons/react";

export function LibrarySection({name, count, sectionKey, search, children, className = "", defaultCollapsed = false}: {
  name: string; count: number; sectionKey: string; search: string; children: ReactNode; className?: string; defaultCollapsed?: boolean;
}) {
  const id = useId();
  const storageKey = `operon-library-collapsed:${sectionKey}`;
  const [collapsed, setCollapsed] = useState(() => {
    try { const saved = localStorage.getItem(storageKey); return saved === null ? defaultCollapsed : saved === "true"; } catch { return defaultCollapsed; }
  });
  const [searchCollapsed, setSearchCollapsed] = useState(false);
  useEffect(() => setSearchCollapsed(false), [search]);
  const expanded = !(search.trim() ? searchCollapsed : collapsed);
  function toggle() {
    if (search.trim()) { setSearchCollapsed(value => !value); return; }
    setCollapsed(!collapsed);
    try { localStorage.setItem(storageKey, String(!collapsed)); } catch { /* Session-only when storage is unavailable. */ }
  }
  return <section className={`library-category ${className} ${expanded ? "is-expanded" : "is-collapsed"}`}>
    <button className="category-title" aria-expanded={expanded} aria-controls={id} onClick={toggle}>
      <CaretDown className="category-chevron" size={12}/><strong>{name}</strong><span>{count}</span>
    </button>
    <div id={id} hidden={!expanded}>{children}</div>
  </section>;
}
