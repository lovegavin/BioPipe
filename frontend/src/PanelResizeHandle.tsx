import { useRef } from "react";
import type { PanelSide } from "./panelLayout";

export function PanelResizeHandle({ side, width, min, max, onResize, onReset, onResizing }: {
  side: PanelSide; width: number; min: number; max: number;
  onResize: (width: number) => void; onReset: () => void; onResizing: (value: boolean) => void;
}) {
  const drag = useRef<{ x: number; width: number } | null>(null);
  const direction = side === "library" ? 1 : -1;
  const resize = (value: number) => onResize(Math.round(Math.max(min, Math.min(max, value))));
  return <div className={`panel-resize-handle resize-${side}`} role="separator" tabIndex={0}
    aria-label={side === "library" ? "调整算子库宽度" : "调整检查器宽度"}
    aria-orientation="vertical" aria-valuemin={min} aria-valuemax={max} aria-valuenow={width}
    aria-valuetext={`${width} 像素`} title="拖动调整宽度 · 双击恢复自动 · 方向键微调"
    onPointerDown={e => {
      if (e.button !== 0) return;
      e.preventDefault(); e.currentTarget.focus(); e.currentTarget.setPointerCapture(e.pointerId);
      drag.current = { x: e.clientX, width }; onResizing(true);
    }}
    onPointerMove={e => { if (drag.current) resize(drag.current.width + direction * (e.clientX - drag.current.x)); }}
    onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); drag.current = null; onResizing(false); }}
    onPointerCancel={() => { if (drag.current) onResize(drag.current.width); drag.current = null; onResizing(false); }}
    onLostPointerCapture={() => { drag.current = null; onResizing(false); }}
    onDoubleClick={onReset}
    onKeyDown={e => {
      const step = e.shiftKey ? 32 : 8;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); resize(width + direction * (e.key === "ArrowRight" ? step : -step)); }
      if (e.key === "Home" || e.key === "End") { e.preventDefault(); resize(e.key === "Home" ? min : max); }
      if (e.key === "Enter") { e.preventDefault(); onReset(); }
    }}><span/></div>;
}
