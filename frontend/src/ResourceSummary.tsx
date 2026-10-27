import {useEffect, useState} from 'react';
import {HardDrives} from '@phosphor-icons/react';
import {api} from './api';
import {bytes} from './graph';
import {targetKey} from './execution';
import type {ExecutionResources} from './types';

export function ResourceSummary() {
  const [resources, setResources] = useState<ExecutionResources | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const load = async () => {
      try {const snapshot = await api.executionResources(); if (alive) {setResources(snapshot); setError('');}}
      catch (e) {if (alive) setError((e as Error).message);}
      if (alive) timer = setTimeout(() => void load(), 3000);
    };
    void load(); return () => {alive = false; clearTimeout(timer);};
  }, []);
  return <div className="resource-summary" aria-label="机器资源">
    {error ? <span className="resource-unavailable" title={error}>资源状态暂不可用</span> : resources?.targets.map(item => <div key={targetKey(item.target)}
      title={`预算 ${bytes(item.capacity_bytes)} · 已分配 ${bytes(item.reserved_bytes)} · CPU ${item.cpu_reserved}/${item.cpu_capacity}`}>
      <HardDrives size={15}/><strong>{item.name || (item.target.kind === 'local' ? '本机' : item.target.profile_id)}</strong>
      <span>{bytes(item.available_bytes)} 可用</span><small>{item.active_jobs} 运行{item.queued_jobs > 0 ? ` · ${item.queued_jobs} 等待` : ''}</small>
    </div>)}
  </div>;
}
