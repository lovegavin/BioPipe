import { useEffect, useRef, useState } from 'react';
import { Package, Plus, Trash, Power, ArrowCounterClockwise, ArrowClockwise, FolderOpen } from '@phosphor-icons/react';
import { Modal } from './RouteDialogs';
import { HelpTip } from './HelpTip';
import { api } from './api';
import type { PluginOperation, PluginState } from './types';

export function PluginPanel({onClose, onChanged}: {onClose: () => void; onChanged: () => Promise<void>}) {
  const [state, setState] = useState<PluginState>({generation: null, packages: [], descriptors: []});
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const busy = pending || !!state.dependencies?.running;
  const file = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    api.plugins().then(value => {if (mounted.current) setState(value);}).catch(e => {if (mounted.current) setError(e.message);});
    return () => {mounted.current = false;};
  }, []);
  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => {void api.plugins().then(value => {if (mounted.current) setState(value);}).catch(() => {});}, 1000);
    return () => clearInterval(timer);
  }, [busy]);
  const dependencyLabels = {unchecked: '待检测', checking: '检测中', installing: '安装中', passed: '依赖就绪', failed: '依赖未就绪'};
  async function operate(begin: () => Promise<PluginOperation>) {
    setPending(true); setError(''); setMessage('正在扫描、校验并更新算子库…');
    try {
      let operation = await begin();
      while (operation.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (!mounted.current) return;
        operation = await api.pluginOperation(operation.id);
      }
      if (operation.status === 'failed') throw Error(operation.error || '插件操作失败');
      const latest = await api.plugins();
      if (mounted.current) {setState(latest); setMessage(operation.result
        ? operation.result.updated.length ? '算子库已更新，即刻可用。' : '没有发现新文件或修改。'
        : latest.dependencies?.entries.some(entry => entry.status === 'failed') ? '依赖检测完成，部分算子需要处理。' : '已完成。');}
      await onChanged();
    } catch (e) {if (mounted.current) {setError((e as Error).message); setMessage('');}}
    finally {if (mounted.current) setPending(false);}
  }
  return <Modal dismissDisabled={pending} title="算子库管理" onClose={() => {if (!pending) onClose();}}>
    <div className="plugin-panel-body">
      <input ref={file} hidden type="file" accept=".whl" onChange={event => {
        const selected = event.target.files?.[0]; event.target.value = '';
        if (selected) void operate(() => api.installPlugin(selected));
      }}/>
      <div className="plugin-toolbar">
        <button className="primary-button" disabled={busy} onClick={() => void operate(api.refreshPlugins)}><ArrowClockwise size={16} className={pending ? 'spin' : ''}/>刷新算子库</button>
        <button className="subtle-button" disabled={busy} onClick={() => file.current?.click()}><Plus size={16}/>导入包</button>
        <button className="subtle-button" disabled={pending || state.dependencies?.running} onClick={() => void operate(api.repairDependencies)}><ArrowClockwise size={16}/>{state.dependencies?.running ? '准备环境…' : '修复依赖'}</button>
        <HelpTip label="算子目录说明">将算子或 Reader 文件放入对应目录，点击刷新即可扫描、校验并加载。也可导入 .whl。代码须来自可信来源；更新失败保留当前算子库。</HelpTip>
      </div>
      <div className="plugin-folder-row">
        <button className="subtle-button" title={state.source_directories?.operator} onClick={() => void api.openPluginFolder('operator').catch(e => setError(e.message))}><FolderOpen size={16}/>算子目录</button>
        <button className="subtle-button" title={state.source_directories?.reader} onClick={() => void api.openPluginFolder('reader').catch(e => setError(e.message))}><FolderOpen size={16}/>Reader 目录</button>
        <button className="subtle-button" title={state.inbox} onClick={() => void api.openPluginFolder('extra').catch(e => setError(e.message))}>附加目录</button>
      </div>
      <div className="plugin-packages">
        {!state.packages.length && <div className="modal-empty"><Package size={30}/><p>尚未安装算子包</p></div>}
        {state.packages.map(item => <article className="plugin-package" key={item.name}>
          <div><strong>{item.title || item.name}</strong><span className="route-version">v{item.version}</span>
            <p>{item.name} · {item.source_managed ? '本地算子' : item.origin === 'bundled' ? '预装' : '已安装'} · {item.enabled === false ? '已禁用' : '已启用'}</p>
            <details><summary>{state.descriptors.filter(d => d.distribution === item.name).length} 个算子 / Reader</summary>
              {state.descriptors.filter(d => d.distribution === item.name).map(d => {
                const dependency = state.dependencies?.entries.find(entry => entry.id === d.id);
                return <div key={d.id}><p>{d.title} <small>{d.resources?.memory_modes.map(mode => ({full: '完整矩阵', stream: '分块流式', disk: '分块落盘'}[mode] || mode)).join(' · ')}{dependency && ` · ${dependencyLabels[dependency.status]}`}</small></p>
                  {dependency?.execution?.mode === 'isolated' && <small title={dependency.execution.reason}>独立依赖进程</small>}
                  {dependency?.status === 'failed' && <pre className="modal-error">{dependency.error}</pre>}</div>;
              })}
            </details>
          </div>
          <div className="plugin-actions">
          <button className="icon-button" title={`${item.enabled === false ? '启用' : '禁用'} ${item.name}`} aria-label={`${item.enabled === false ? '启用' : '禁用'} ${item.name}`} disabled={busy} onClick={() => void operate(() => api.managePlugin(item.name, item.enabled === false ? 'enable' : 'disable'))}><Power size={17}/></button>
          <button className="icon-button" title={`移除 ${item.name}`} aria-label={`移除 ${item.name}`} disabled={busy} onClick={() => void operate(() => api.removePlugin(item.name))}><Trash size={17}/></button>
          </div>
        </article>)}
        {state.bundled_packages?.filter(item => !state.packages.some(p => p.name === item.name && (p.origin === 'bundled' || p.source_managed))).map(item =>
          <article className="plugin-package" key={'restore-' + item.name}><div><strong>{item.title || item.name}</strong><p>可恢复预装版本 v{item.version}</p></div>
            <button className="subtle-button" disabled={busy} onClick={() => void operate(() => api.managePlugin(item.name, 'restore'))}><ArrowCounterClockwise size={15}/>恢复</button></article>)}
      </div>
      {message && <p role="status" className="plugin-status">{message}</p>}
      {error && <p role="alert" className="modal-error">{error}</p>}
    </div>
    <footer><span className="modal-spacer"/><button className="subtle-button" disabled={pending} onClick={onClose}>完成</button></footer>
  </Modal>;
}
