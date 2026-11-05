import {useEffect, useRef, useState} from 'react';
import {ArrowSquareOut, CaretDown, Gear, Monitor, ArrowsClockwise} from '@phosphor-icons/react';
import {api} from './api';
import './viewers.css';

export type Viewer = {id: string; name: string; kind: 'desktop' | 'web'; mode: 'file' | 'manual';
  available: boolean; status: string; notes: string; executable: string | null; url?: string; source: string};
const statusText: Record<string, string> = {not_found: '设置程序位置', unsupported_system: '当前系统不支持', java_required: '需要 Java', desktop_required: '需要桌面会话'};

export function ResultViewers({job, artifact, role}: {job: string; artifact: string; role: string}) {
  const [open, setOpen] = useState(false);
  const [viewers, setViewers] = useState<Viewer[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [configure, setConfigure] = useState<string | null>(null);
  const [program, setProgram] = useState('');
  const [path, setPath] = useState('');
  const [message, setMessage] = useState('');
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current;
    setPath(''); setMessage(''); setViewers(null); setError(''); setBusy(false); setConfigure(null);
    if (open) api.artifactViewers(job, artifact, role).then(r => {
      if (generation.current === current) setViewers(r.viewers);
    }).catch(e => {if (generation.current === current) setError(String(e.message || e));});
    return () => {generation.current++;};
  }, [open, job, artifact, role]);
  async function act(action: () => Promise<void>) {
    const current = generation.current;
    setBusy(true); setError(''); setMessage('');
    try {await action();} catch (e) {if (generation.current === current) setError(e instanceof Error ? e.message : String(e));}
    finally {if (generation.current === current) setBusy(false);}
  }
  async function load(refresh = false) {
    const current = generation.current;
    if (refresh) await api.viewers(true);
    const result = await api.artifactViewers(job, artifact, role);
    if (generation.current === current) setViewers(result.viewers);
  }
  async function launch(viewer: Viewer) {
    const current = generation.current;
    const result = await api.openViewer(job, artifact, role, viewer.id);
    if (generation.current !== current) return;
    setPath(result.path);
    setMessage(result.mode === 'manual' ? '已启动，请在软件中打开下方文件' : '已发送打开请求');
  }
  return <div className="result-viewers">
    <button className="text-button" aria-expanded={open} onClick={() => setOpen(!open)}><Monitor size={14}/>打开方式<CaretDown size={12}/></button>
    {open && <div className="viewer-panel" aria-label="结果查看器">
      <div className="viewer-heading"><span>桌面软件</span><button title="重新检测已安装的软件" aria-label="刷新查看器" disabled={busy} onClick={() => void act(() => load(true))}><ArrowsClockwise size={14}/></button></div>
      {viewers === null && !error && <span role="status">正在检测…</span>}
      {viewers?.filter(v => v.kind === 'desktop').map(v => <div className="viewer-row" key={v.id}>
        <button title={v.notes} disabled={busy || !v.available} onClick={() => void act(() => launch(v))}><span>{v.name}</span><small>{v.available ? (v.mode === 'file' ? '打开文件' : '启动 · 手动打开') : statusText[v.status] || v.status}</small></button>
        {v.status !== 'unsupported_system' && <button aria-label={`设置 ${v.name}`} title="设置程序位置" disabled={busy} onClick={() => {setConfigure(v.id); setProgram(v.executable || '');}}><Gear size={14}/></button>}
      </div>)}
      {viewers && !viewers.some(v => v.kind === 'desktop') && <span>此格式暂无桌面适配器</span>}
      {configure && <form className="viewer-config" onSubmit={e => {e.preventDefault(); void act(async () => {await api.configureViewer(configure, program.trim() || null); setConfigure(null); await load();});}}>
        <label>程序位置<input autoFocus aria-label="程序位置" placeholder="EXE / GUI JAR 完整路径" value={program} onChange={e => setProgram(e.target.value)}/></label>
        <div><button disabled={busy} type="submit">保存</button><button type="button" disabled={busy} onClick={() => setConfigure(null)}>取消</button></div>
      </form>}
      {viewers?.some(v => v.kind === 'web') && <details className="viewer-web"><summary>网页查看器</summary>{viewers.filter(v => v.kind === 'web').map(v => <a key={v.id} href={v.url} target="_blank" rel="noreferrer" title={v.notes}>{v.name}<span>手动导入</span><ArrowSquareOut size={13}/></a>)}</details>}
      <button className="text-button viewer-path" disabled={busy} onClick={() => void act(async () => {const current = generation.current; const r = await api.prepareViewer(job, artifact, role); if (generation.current === current) setPath(r.path);})}>获取文件位置</button>
      {busy && <span role="status">正在处理；服务器结果需先传到本机…</span>}
      {message && <span role="status">{message}</span>}
      {path && <div className="viewer-location"><input readOnly aria-label="结果文件位置" value={path} onFocus={e => e.currentTarget.select()}/><button onClick={() => void act(async () => {await navigator.clipboard.writeText(path); setMessage('已复制文件位置');})}>复制</button></div>}
      {error && <span className="viewer-error" role="alert">{error}</span>}
    </div>}
  </div>;
}
