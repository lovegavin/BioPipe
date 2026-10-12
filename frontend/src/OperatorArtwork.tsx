import type { ReactNode } from "react";
import type { Operator } from "./types";
import { OperatorIcon } from "./icons";

const axes = <path d="M7 5v33h51" opacity=".25"/>;
const dots = (points: number[][], radius = 1.6, opacity = 1) => points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={radius} fill="currentColor" stroke="none" opacity={opacity}/>);
// Small, deterministic diagrams: these illustrate chart families, not run data.
const charts: Record<string, ReactNode> = {
  scatter: <>{axes}{dots([[13,30],[17,25],[20,31],[24,23],[28,26],[31,17],[36,22],[39,13],[43,18],[48,10],[53,15]], 1.9)}</>,
  histogram: <>{axes}<g fill="currentColor" stroke="none" opacity=".65"><path d="M11 37V31h6v6zM19 37V22h6v15zM27 37V10h6v27zM35 37V15h6v22zM43 37V26h6v11zM51 37V33h5v4z"/></g></>,
  line: <>{axes}<path d="m11 31 9-8 9 4 8-15 9 5 9-10"/>{dots([[11,31],[20,23],[29,27],[37,12],[46,17],[55,7]], 1.7)}</>,
  manhattan: <>{axes}<path d="M9 17h49" strokeDasharray="2 3" opacity=".3"/>{dots([[12,31],[14,28],[16,32],[18,22],[20,15],[22,8],[24,23],[26,30],[28,33],[30,28],[32,32],[35,26],[37,17],[39,24],[41,30],[44,33],[46,29],[48,25],[50,14],[52,6],[54,19],[56,31]], 1.35)}</>,
  volcano: <>{axes}<path d="M10 23h48M25 7v29M40 7v29" strokeDasharray="2 3" opacity=".23"/>{dots([[24,30],[27,33],[30,29],[33,32],[36,31],[39,29],[22,26],[42,26]], 1.5, .4)}{dots([[12,9],[15,14],[17,20],[19,15],[21,22],[43,20],[46,15],[49,18],[52,9],[55,12]], 1.9)}</>,
  ma: <>{axes}<path d="M9 22h49" strokeDasharray="2 3" opacity=".3"/>{dots([[12,8],[12,35],[15,18],[17,12],[18,30],[20,22],[23,17],[24,28],[27,21],[29,25],[32,19],[35,24],[39,21],[43,24],[47,20],[51,23],[55,21]], 1.7)}</>,
  heatmap: <><path d="M6 11h3V7h5M6 19h3v8H6M14 4v-2h14v2M37 4v-2h17v2" opacity=".4"/>{[.8,.5,.15,.3,.75,.35,.65,.85,.25,.45,.2,.8,.55,.9,.3,.6,.35,.8,.4,.15].map((opacity,i) => <rect key={i} x={13+(i%5)*8.5} y={7+Math.floor(i/5)*8.5} width={7} height={7} rx={.8} fill="currentColor" stroke="none" opacity={opacity}/>)}</>,
  boxplot: <>{axes}<path d="M20 9v7m-4-7h8m-4 18v7m-4 0h8M43 5v7m-4-7h8m-4 18v8m-4 0h8" opacity=".7"/><path d="M15 16h10v11H15zM38 12h10v11H38z" fill="currentColor" fillOpacity=".1"/><path d="M15 21h10m13-4h10"/>{dots([[43,35]],1.1)}</>,
  survival: <>{axes}<path d="M10 9h8v4h10v7h9v4h8v7h11"/><path d="M10 13h6v8h8v7h11v6h16" opacity=".35"/><path d="M23 11v4m18 7v4m10 3v4"/></>,
  forest: <><path d="M33 4v35" strokeDasharray="2 3" opacity=".3"/><path d="M17 10h29M12 20h22M29 30h27" opacity=".65"/><path d="M17 8v4m29-4v4M12 18v4m22-4v4M29 28v4m27-4v4" opacity=".5"/><g fill="currentColor" stroke="none"><rect x="25" y="7" width="6" height="6" rx=".7"/><rect x="20" y="17" width="6" height="6" rx=".7"/><path d="m42 26 5 4-5 4-5-4z"/></g><path d="M9 38h49" opacity=".25"/></>,
};

export function ChartGlyph({ kind, className = "" }: { kind: string; className?: string }) {
  if (!charts[kind]) return null;
  return <svg className={`chart-glyph ${className}`} viewBox="0 0 64 44" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{charts[kind]}</svg>;
}

export function OperatorArtwork({ spec, source, size = 20 }: { spec?: Operator; source?: boolean; size?: number }) {
  return !source && spec?.preview && charts[spec.preview.kind]
    ? <ChartGlyph kind={spec.preview.kind}/>
    : <OperatorIcon name={source ? "Database" : spec?.icon} size={size}/>;
}

export function OperatorPreview({ spec }: { spec?: Operator }) {
  if (!spec?.preview || !charts[spec.preview.kind]) return null;
  return <figure className="operator-preview">
    <ChartGlyph kind={spec.preview.kind}/>
    <figcaption><span>{spec.preview.caption}</span><small>图形示意</small></figcaption>
  </figure>;
}
