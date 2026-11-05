import {t} from './i18n';
import {useEffect, useState} from 'react';
import {ArrowsClockwise, MagnifyingGlass, Monitor, X} from '@phosphor-icons/react';
import {api} from './api';
import {viewerStatus, type ViewerCatalog, type Viewer} from './viewerTypes';

function ProgramLocation({viewer, busy, save}: {viewer: Viewer; busy: boolean; save: (id: string, path: string | null) => Promise<void>}) {
  const [path, setPath] = useState(viewer.configured_path || viewer.executable || '');
  useEffect(() => {setPath(viewer.configured_path || viewer.executable || '');}, [viewer.configured_path, viewer.executable]);
  return <details className="program-location">
    <summary><Monitor size={18}/><span><strong>{viewer.name}</strong><small>{viewer.domain}</small></span>
      <span className={`program-status${viewer.available ? ' available' : ''}`}>{viewer.available ? t("可用") : t(viewerStatus[viewer.status] || viewer.status)}</span></summary>
    <form onSubmit={e => {e.preventDefault(); void save(viewer.id, path.trim() || null);}}>
      <label className="field"><span>{t("程序位置")}</span><input aria-label={t("{v0} 程序位置", {v0: viewer.name})} placeholder={t("EXE / GUI JAR 完整路径")} value={path} disabled={busy} onChange={e => setPath(e.target.value)}/></label>
      <div className="settings-form-actions"><button className="subtle-button" type="button" disabled={busy || !viewer.configured_path} onClick={() => void save(viewer.id, null)}>{t("恢复自动检测")}</button>
        <button className="primary-button" type="submit" disabled={busy || viewer.status === 'unsupported_system'}>{t("保存位置")}</button></div>
      <p className="settings-note">{viewer.notes}</p>
    </form>
  </details>;
}

export function ViewerSettings({onBusyChange}: {onBusyChange: (busy: boolean) => void}) {
  const [catalog, setCatalog] = useState<ViewerCatalog | null>(null);
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const [search, setSearch] = useState(''), [extension, setExtension] = useState('.hic'), [choice, setChoice] = useState('');
  useEffect(() => {let alive = true; api.viewers().then(value => {if (alive) {setCatalog(value); setChoice(value.defaults['.hic'] || '');}})
    .catch(e => {if (alive) setError(e.message);}); return () => {alive = false;};}, []);
  useEffect(() => {onBusyChange(busy);}, [busy, onBusyChange]);
  async function update(action: () => Promise<ViewerCatalog>, success: string) {
    setBusy(true); setError(''); setMessage('');
    try {const value = await action(); setCatalog(value); setChoice(value.defaults[extension] || ''); setMessage(success);}
    catch(e) {setError(e instanceof Error ? e.message : String(e));}
    finally {setBusy(false);}
  }
  const desktop = catalog?.viewers.filter(v => v.kind === 'desktop') || [];
  const extensions = [...new Set([...desktop.flatMap(v => v.extensions), ...Object.keys(catalog?.defaults || {})])].sort();
  const compatible = desktop.filter(v => v.extensions.includes(extension));
  const currentExists = !choice || compatible.some(v => v.id === choice);
  return <div className="viewer-settings">
    <div className="settings-section-heading"><h3>{t("默认打开方式")}</h3><button className="subtle-button" disabled={busy} onClick={() => void update(() => api.viewers(true), t("已重新检测"))}><ArrowsClockwise size={15}/>{t("重新检测")}</button></div>
    <p className="settings-note">{t("点击结果的“打开”时使用。网页查看器仍可从菜单中选择。")}</p>
    {!catalog && !error && <p role="status">{t("正在读取查看器…")}</p>}
    {catalog && <>
      <form className="default-viewer-form" onSubmit={e => {e.preventDefault(); void update(() => api.defaultViewer(extension, choice || null), t("默认打开方式已保存"));}}>
        <label className="field"><span>{t("文件格式")}</span><select aria-label={t("文件格式")} disabled={busy} value={extension} onChange={e => {setExtension(e.target.value); setChoice(catalog.defaults[e.target.value] || ''); setMessage('');}}>
          {extensions.map(value => <option key={value} value={value}>{value}</option>)}
        </select></label>
        <label className="field"><span>{t("打开方式")}</span><select aria-label={t("默认查看器")} disabled={busy} value={choice} onChange={e => setChoice(e.target.value)}>
          <option value="">{t("自动 · 优先可用桌面软件")}</option>
          {!currentExists && <option value={choice}>{choice} {t("· 已不可用")}</option>}
          {compatible.map(v => <option key={v.id} value={v.id} disabled={v.status === 'unsupported_system'}>{v.name}{v.available ? '' : ` · ${t(viewerStatus[v.status] || v.status)}`}</option>)}
        </select></label>
        <button className="primary-button" type="submit" disabled={busy || !currentExists}>{t("保存")}</button>
      </form>
      {Object.keys(catalog.defaults).length > 0 && <div className="saved-viewer-defaults" aria-label={t("已保存的打开方式")}>
        {Object.entries(catalog.defaults).sort(([a], [b]) => a.localeCompare(b)).map(([suffix, id]) => <div key={suffix}>
          <button title={t("编辑 {v0} 打开方式", {v0: suffix})} disabled={busy} onClick={() => {setExtension(suffix); setChoice(id);}}><code>{suffix}</code><span>{desktop.find(v => v.id === id)?.name || id}</span></button>
          <button className="icon-button" disabled={busy} aria-label={t("清除 {v0} 默认打开方式", {v0: suffix})} onClick={() => void update(() => api.defaultViewer(suffix, null), t("已恢复自动选择"))}><X size={13}/></button>
        </div>)}
      </div>}
    </>}
    <div className="settings-feedback" aria-live="polite">{error ? <p className="field-error" role="alert">{error}</p> : <p role="status">{busy ? t("正在保存…") : message}</p>}</div>
    <div className="settings-section-heading"><h3>{t("程序位置")}</h3><span>{desktop.filter(v => v.available).length} / {desktop.length} {t("可用")}</span></div>
    <label className="search-field"><MagnifyingGlass size={16}/><input aria-label={t("搜索查看器")} placeholder={t("搜索软件或文件格式")} value={search} onChange={e => setSearch(e.target.value)}/></label>
    <div className="program-list">{desktop.filter(v => `${v.name} ${v.domain} ${v.extensions.join(' ')}`.toLowerCase().includes(search.toLowerCase())).map(v =>
      <ProgramLocation key={v.id} viewer={v} busy={busy} save={(id, path) => update(() => api.configureViewer(id, path), t("程序位置已保存"))}/>)}</div>
  </div>;
}
