import {useState} from 'react';
import {Check, CircleNotch, HardDrives, Path} from '@phosphor-icons/react';
import {api} from './api';
import {ResourceSummary} from './ResourceSummary';
import {bytes} from './graph';
import {defaultTarget, executionConfig, targetFromKey, targetKey, targetLabel} from './execution';
import type {ExecutionConfig, ExecutionPlan, Graph, RemoteStatus, TargetRef} from './types';

export function EnvironmentMenu({graph, nodeId, servers, onSelect}: {
  graph: Graph; nodeId: string; servers: RemoteStatus[]; onSelect: (target?: TargetRef) => void;
}) {
  const config = executionConfig(graph), automatic = config.mode === 'auto';
  const selected = config.node_targets?.[nodeId];
  const node = graph.nodes.find(item => item.id === nodeId);
  if (!node || node.kind === 'source') return null;
  const targets: {target?: TargetRef; label: string}[] = [{label: '跟随默认环境'},
    {target: {kind: 'local'}, label: '本机'}, ...servers.map(server => ({target: {kind: 'ssh', profile_id: server.profile.id!} as TargetRef,
      label: server.profile.name + (server.connected ? '' : ' · 离线')}))];
  return <>
    <div className="menu-line"/>
    <div className="context-caption">{node.kind === 'route' ? '整条路线环境' : '运行环境'}{automatic ? ' · 自动分配' : ''}</div>
    {targets.map(({target, label}, index) => <button key={index} role="menuitemradio" disabled={automatic}
      aria-checked={target ? !!selected && targetKey(selected) === targetKey(target) : !selected}
      onClick={() => onSelect(target)}>
      <span className="environment-check">{(target ? !!selected && targetKey(selected) === targetKey(target) : !selected) && <Check size={15}/>}</span>{label}
    </button>)}
  </>;
}

export function ExecutionSettings({graph, servers, disabled, onChange}: {
  graph: Graph; servers: RemoteStatus[]; disabled: boolean; onChange: (patch: Partial<ExecutionConfig>) => void;
}) {
  const config = executionConfig(graph);
  const [preview, setPreview] = useState<{signature: string; plan: ExecutionPlan} | null>(null);
  const [loading, setLoading] = useState(false), [error, setError] = useState('');
  const signature = JSON.stringify(graph);
  const plan = preview?.signature === signature ? preview.plan : undefined;
  async function inspect() {
    setLoading(true); setError('');
    try {setPreview({signature, plan: await api.executionPlan(graph)});}
    catch (value) {setError((value as Error).message);}
    finally {setLoading(false);}
  }
  return <section className="execution-settings" aria-label="运行环境设置">
    <div className="inspector-intro"><div className="node-icon"><HardDrives size={20}/></div><h3>运行环境</h3></div>
    <div className="segmented" role="group" aria-label="环境分配方式">
      <button aria-pressed={config.mode === 'auto'} disabled={disabled} className={config.mode === 'auto' ? 'active' : ''}
        onClick={() => onChange({mode: 'auto'})}>自动</button>
      <button aria-pressed={config.mode === 'manual'} disabled={disabled} className={config.mode === 'manual' ? 'active' : ''}
        onClick={() => onChange({mode: 'manual'})}>手动</button>
    </div>
    <label className="field"><span>{config.mode === 'auto' ? '优先环境' : '默认环境'}</span>
      <select aria-label="默认运行环境" value={targetKey(defaultTarget(graph))} disabled={disabled}
        onChange={e => onChange({...targetFromKey(e.target.value), profile_id: e.target.value || undefined})}>
        <option value="">本机</option>
        {config.profile_id && !servers.some(server => server.profile.id === config.profile_id) && <option value={config.profile_id}>未配置的服务器</option>}
        {servers.map(server => <option value={server.profile.id} key={server.profile.id}>{server.profile.name}{server.connected ? '' : ' · 离线'}</option>)}
      </select>
    </label>
    <label className="field"><span>并行任务上限 <small>可选</small></span>
      <input aria-label="并行任务上限" type="number" min="1" step="1" placeholder="按可用资源" disabled={disabled}
        value={config.max_parallel_tasks ?? ''} onChange={e => onChange({max_parallel_tasks: e.target.value ? Math.max(1, Math.floor(Number(e.target.value))) : undefined})}/>
    </label>
    <button type="button" className="subtle-button execution-preview-button" disabled={disabled || loading || !graph.nodes.length} onClick={() => void inspect()}>
      {loading ? <CircleNotch size={16} className="spin"/> : <Path size={16}/>}预览环境分配
    </button>
    {error && <p className="field-error" role="alert">{error}</p>}
    {plan && <div className="execution-preview">
      {plan.units.map(unit => <div key={unit.id} title={unit.reason}>
        <span>{unit.node_ids.map(id => graph.nodes.find(node => node.id === id)?.title || id).join(' · ')}</span>
        <strong>{targetLabel(unit.target, servers)}</strong>
        {unit.estimated_bytes != null && unit.estimated_bytes > 0 && <small>{bytes(unit.estimated_bytes)}</small>}
      </div>)}
      {!!plan.transfers.length && <p>{plan.transfers.length} 次数据传输</p>}
      {plan.warnings.map((warning, index) => <p key={index} className="field-error">{warning}</p>)}
    </div>}
    <ResourceSummary/>
    <div className="section-rule"/>
  </section>;
}
