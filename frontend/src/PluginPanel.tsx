import { useEffect, useRef, useState } from 'react';
import { Package, Plus, Trash, Power, ArrowCounterClockwise } from '@phosphor-icons/react';
import { Modal } from './RouteDialogs';
import { HelpTip } from './HelpTip';
import { api } from './api';
import type { PluginOperation, PluginState } from './types';

export function PluginPanel({onClose, onChanged}: {onClose: () => void; onChanged: () => Promise<void>}) {
  const [state, setState] = useState<PluginState>({generation: null, packages: [], descriptors: []});
  const [pending, setPending] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('');
  const file = useRef<HTMLInputElement>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    api.plugins().then(value => {if (mounted.current) setState(value);}).catch(e => {if (mounted.current) setError(e.message);});
    return () => {mounted.current = false;};
  }, []);
  async function operate(begin: () => Promise<PluginOperation>) {
    setPending(true); setError(''); setMessage('正在准备插件环境，完成后自动刷新算子库…');
    try {
      let operation = await begin();
      while (operation.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        if (!mounted.current) return;
        operation = await api.pluginOperation(operation.id);
      }
      if (operation.status === 'failed') throw Error(operation.error || '插件操作失败');
      const latest = await api.plugins();
      if (mounted.current) {setState(latest); setMessage('已完成，算子库已更新。');}
      await onChanged();
    } catch (e) {if (mounted.current) {setError((e as Error).message); setMessage('');}}
    finally {if (mounted.current) setPending(false);}
  }
  return <Modal dismissDisabled={pending} title="算子包管理" onClose={() => {if (!pending) onClose();}}>
    <div className="plugin-panel-body">
      <input ref={file} hidden type="file" accept=".whl" onChange={event => {
        const selected = event.target.files?.[0]; event.target.value = '';
        if (selected) void operate(() => api.installPlugin(selected));
      }}/>
      <div className="plugin-toolbar">
        <button className="primary-button" disabled={pending} onClick={() => file.current?.click()}><Plus size={16}/>安装 / 更新包</button>
        <span className="route-version">.whl</span>
        <HelpTip label="算子包说明">插件会运行 Python 代码，请选择可信来源。安装与更新即时生效；禁用或移除后，已锁定版本的画布与运行中任务保留原环境。预装包可恢复。</HelpTip>
      </div>
      <div className="plugin-packages">
        {!state.packages.length && <div className="modal-empty"><Package size={30}/><p>尚未安装算子包</p></div>}
        {state.packages.map(item => <article className="plugin-package" key={item.name}>
          <div><strong>{item.title || item.name}</strong><span className="route-version">v{item.version}</span>
            <p>{item.name} · {item.origin === 'bundled' ? '预装' : '已安装'} · {item.enabled === false ? '已禁用' : '已启用'}</p>
            <details><summary>{state.descriptors.filter(d => d.distribution === item.name).length} 个算子 / Reader</summary>
              {state.descriptors.filter(d => d.distribution === item.name).map(d => <p key={d.id}>{d.title} <small>{d.resources?.memory_modes.map(mode => ({full: '完整矩阵', stream: '分块流式', disk: '分块落盘'}[mode] || mode)).join(' · ')}</small></p>)}
            </details>
          </div>
          <div className="plugin-actions">
          <button className="icon-button" title={`${item.enabled === false ? '启用' : '禁用'} ${item.name}`} aria-label={`${item.enabled === false ? '启用' : '禁用'} ${item.name}`} disabled={pending} onClick={() => void operate(() => api.managePlugin(item.name, item.enabled === false ? 'enable' : 'disable'))}><Power size={17}/></button>
          <button className="icon-button" title={`移除 ${item.name}`} aria-label={`移除 ${item.name}`} disabled={pending} onClick={() => void operate(() => api.removePlugin(item.name))}><Trash size={17}/></button>
          </div>
        </article>)}
        {state.bundled_packages?.filter(item => !state.packages.some(p => p.name === item.name && p.origin === 'bundled')).map(item =>
          <article className="plugin-package" key={'restore-' + item.name}><div><strong>{item.title || item.name}</strong><p>可恢复预装版本 v{item.version}</p></div>
            <button className="subtle-button" disabled={pending} onClick={() => void operate(() => api.managePlugin(item.name, 'restore'))}><ArrowCounterClockwise size={15}/>恢复</button></article>)}
      </div>
      {message && <p role="status" className="plugin-status">{message}</p>}
      {error && <p role="alert" className="modal-error">{error}</p>}
    </div>
    <footer><span className="modal-spacer"/><button className="subtle-button" disabled={pending} onClick={onClose}>完成</button></footer>
  </Modal>;
}
