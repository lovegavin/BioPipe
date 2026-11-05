import {useEffect, useRef, useState} from 'react';
import {ArrowClockwise, FileArrowUp, FolderOpen, Package, Plus, Stack} from '@phosphor-icons/react';
import {api} from './api';
import {normalizeGraph} from './graph';
import type {PluginState, WorkflowSummary} from './types';
import {t} from './i18n';

export function AddOperators({state, busy, onPackage, onRefresh, onChanged, onPending, onError, onMessage}: {
  state: PluginState; busy: boolean; onPackage: () => void; onRefresh: () => void;
  onChanged: () => Promise<void>; onPending: (value: boolean) => void;
  onError: (value: string) => void; onMessage: (value: string) => void;
}) {
  const [routes, setRoutes] = useState<WorkflowSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]), [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const file = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    api.workflows().then(items => {if (active) setRoutes(items);}).catch(error => {if (active) onError(error.message);})
      .finally(() => {if (active) setLoading(false);});
    return () => {active = false;};
  }, []);
  async function register(files?: File[]) {
    onPending(true); onError(''); onMessage('');
    // Save each imported graph once; failures leave it available for retry.
    const saved: string[] = [];
    try {
      if (files) for (const item of files) {
        const graph = normalizeGraph(item.name.toLowerCase().endsWith('.zip')
          ? await api.importWorkflow(item) : JSON.parse(await item.text()));
        saved.push((await api.saveWorkflow(graph)).id);
      }
      await api.registerRoutes(files ? saved : selected);
      setSelected([]);
      onMessage(t('路线算子已添加，即刻可用。'));
    } catch (error) {onError((error as Error).message); if (saved.length) setSelected(saved);}
    finally {
      try {setRoutes(await api.workflows()); await onChanged();}
      catch (error) {onError((error as Error).message);}
      onPending(false);
    }
  }
  const visible = routes.filter(route => route.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <div className="add-operators">
    <section className="operator-install-card">
      <div className="operator-install-heading"><span><Package size={24}/></span><div><h3>{t('普通算子与 Reader')}</h3><code>.whl · .biopipe-library.zip</code></div>
        <button className="primary-button" disabled={busy} onClick={onPackage}><FileArrowUp size={16}/>{t('导入包')}</button></div>
      <div className="plugin-folder-row">
        <button className="subtle-button" title={state.source_directories?.operator} onClick={() => void api.openPluginFolder('operator').catch(e => onError(e.message))}><FolderOpen size={16}/>{t('算子目录')}</button>
        <button className="subtle-button" title={state.source_directories?.reader} onClick={() => void api.openPluginFolder('reader').catch(e => onError(e.message))}><FolderOpen size={16}/>{t('Reader 目录')}</button>
        <button className="subtle-button" title={state.inbox} onClick={() => void api.openPluginFolder('extra').catch(e => onError(e.message))}><FolderOpen size={16}/>{t('附加目录')}</button>
        <button className="subtle-button" disabled={busy} onClick={onRefresh}><ArrowClockwise size={16}/>{t('扫描新增算子')}</button>
      </div>
    </section>
    <section className="operator-install-card">
      <div className="operator-install-heading"><span><Stack size={24}/></span><div><h3>{t('路线算子')}</h3><code>.json · .biopipe.zip</code></div>
        <button className="subtle-button" disabled={busy} onClick={() => file.current?.click()}><FileArrowUp size={16}/>{t('导入路线文件')}</button></div>
      <input hidden ref={file} type="file" multiple accept=".json,.zip" onChange={event => {
        const files = Array.from(event.target.files || []); event.target.value = '';
        if (files.length) void register(files);
      }}/>
      <div className="saved-operator-routes">
        <input type="search" className="route-search" aria-label={t('搜索已保存路线')} placeholder={t('搜索已保存路线')} value={search} onChange={e => setSearch(e.target.value)}/>
        <div className="add-route-list">
          {!visible.length && <div className="modal-empty"><Stack size={24}/><p>{loading ? t('正在读取保存的路线…') : search ? t('没有匹配的路线') : t('暂无已保存路线')}</p></div>}
          {visible.map(route => <label className={`workflow-choice ${selected.includes(route.id) ? 'checked' : ''}`} key={route.id}>
            <input type="checkbox" disabled={busy || loading} checked={selected.includes(route.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, route.id] : ids.filter(id => id !== route.id))}/>
            <span className="workflow-choice-text"><strong>{route.name}</strong><small>{t('{count} 个节点', {count: route.nodes})} · v{route.version}</small></span>
            {route.registered_version && <span className="route-version">{route.registered_version === route.version ? t('已注册') : t('可更新')}</span>}
          </label>)}
        </div>
        <div className="add-route-actions"><span>{selected.length > 0 && t('已选 {count} 条', {count: selected.length})}</span><button className="primary-button" disabled={busy || loading || !selected.length} onClick={() => void register()}><Plus size={16}/>{t('添加到算子库')}</button></div>
      </div>
    </section>
  </div>;
}
