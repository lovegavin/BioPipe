import {t} from './i18n';
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
  return <div className="resource-summary" aria-label={t("机器资源")}>
    {error ? <span className="resource-unavailable" title={error}>{t("资源状态暂不可用")}</span> : resources?.targets.map(item => <div key={targetKey(item.target)}
      title={t("预算 {v0} · 已分配 {v1} · CPU {v2}/{v3}", {v0: bytes(item.capacity_bytes), v1: bytes(item.reserved_bytes), v2: item.cpu_reserved, v3: item.cpu_capacity})}>
      <HardDrives size={15}/><strong>{item.name || (item.target.kind === 'local' ? t("本机") : item.target.profile_id)}</strong>
      <span>{bytes(item.available_bytes)} {t("可用")}</span><small>{item.active_jobs} {t("运行")}{item.queued_jobs > 0 ? t(" · {v0} 等待", {v0: item.queued_jobs}) : ''}</small>
    </div>)}
  </div>;
}
