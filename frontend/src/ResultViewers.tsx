import {t} from './i18n';
import {useEffect, useRef, useState} from 'react';
import {ArrowSquareOut, CaretDown, Gear, Monitor} from '@phosphor-icons/react';
import {api} from './api';
import {viewerStatus, type ViewerOptions} from './viewerTypes';
export type {Viewer} from './viewerTypes';
import './viewers.css';

export function ResultViewers({job, artifact, role, onSettings}: {job: string; artifact: string; role: string; onSettings?: () => void}) {
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState<ViewerOptions | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [path, setPath] = useState(''), [message, setMessage] = useState('');
  const generation = useRef(0);
  useEffect(() => {
    generation.current++; setOpen(false); setOptions(null); setPath(''); setMessage(''); setError(''); setBusy(false);
    return () => {generation.current++;};
  }, [job, artifact, role]);
  useEffect(() => {
    if (!open) return;
    let alive = true;
    api.artifactViewers(job, artifact, role).then(r => {if (alive) setOptions(r);})
      .catch(e => {if (alive) setError(String(e.message || e));});
    return () => {alive = false;};
  }, [open, job, artifact, role]);
  async function act(action: (current: number) => Promise<void>) {
    const current = generation.current;
    setBusy(true); setError(''); setMessage('');
    try {await action(current);} catch(e) {if (generation.current === current) {setError(e instanceof Error ? e.message : String(e)); setOpen(true);}}
    finally {if (generation.current === current) setBusy(false);}
  }
  async function launch(current: number, viewer?: string) {
    const result = await api.openViewer(job, artifact, role, viewer);
    if (generation.current !== current) return;
    setPath(result.path); setMessage(result.mode === 'manual' ? t("已启动，请在软件中打开下方文件") : t("已发送打开请求"));
    if (result.mode === 'manual') setOpen(true);
  }
  return <div className="result-viewers">
    <div className="viewer-open-actions"><button className="text-button" disabled={busy} title={t("使用默认查看器打开")} onClick={() => void act(current => launch(current))}><Monitor size={14}/>{busy ? t("正在打开…") : t("打开")}</button>
      <button className="icon-button" aria-label={t("其他打开方式")} title={t("其他打开方式")} aria-expanded={open} onClick={() => setOpen(!open)}><CaretDown size={12}/></button></div>
    {!open && (message || error) && <span className="viewer-inline-status" role="status">{error || message}</span>}
    {open && <div className="viewer-panel" aria-label={t("结果查看器")}>
      <div className="viewer-heading"><span>{t("桌面软件")}</span></div>
      {options === null && !error && <span role="status">{t("正在检测…")}</span>}
      {options?.viewers.filter(v => v.kind === 'desktop').map(v => <div className="viewer-row" key={v.id}>
        <button title={v.notes} disabled={busy || !v.available} onClick={() => void act(current => launch(current, v.id))}><span>{v.name}{options.default_viewer === v.id && <small> {t("· 默认")}</small>}</span><small>{v.available ? (v.mode === 'manual' ? t("手动打开") : '') : t(viewerStatus[v.status] || v.status)}</small></button>
      </div>)}
      {options && !options.viewers.some(v => v.kind === 'desktop') && <span>{t("此格式暂无桌面适配器")}</span>}
      {options?.viewers.some(v => v.kind === 'web') && <details className="viewer-web"><summary>{t("网页查看器")}</summary>{options.viewers.filter(v => v.kind === 'web').map(v => <a key={v.id} href={v.url} target="_blank" rel="noreferrer" title={v.notes}>{v.name}<span>{t("手动导入")}</span><ArrowSquareOut size={13}/></a>)}</details>}
      <button className="text-button viewer-path" disabled={busy} onClick={() => void act(async current => {const r = await api.prepareViewer(job, artifact, role); if (generation.current === current) setPath(r.path);})}>{t("获取文件位置")}</button>
      {onSettings && <button className="text-button viewer-settings-link" onClick={() => {setOpen(false); onSettings();}}><Gear size={14}/>{t("管理打开方式")}</button>}
      {busy && <span role="status">{t("正在处理；服务器结果需先传到本机…")}</span>}
      {message && <span role="status">{message}</span>}
      {path && <div className="viewer-location"><input readOnly aria-label={t("结果文件位置")} value={path} onFocus={e => e.currentTarget.select()}/><button onClick={() => void act(async current => {await navigator.clipboard.writeText(path); if (generation.current === current) setMessage(t("已复制文件位置"));})}>{t("复制")}</button></div>}
      {error && <span className="viewer-error" role="alert">{error}</span>}
    </div>}
  </div>;
}
