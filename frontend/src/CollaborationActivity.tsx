import {useState} from 'react';
import {ArrowCounterClockwise, ClockCounterClockwise, X} from '@phosphor-icons/react';
import {api} from './api';
import {t} from './i18n';
import type {CanvasEvent, ChangePreview} from './agentBridge';
import './collaboration.css';

export function mergeActivity(previous: CanvasEvent[], incoming: CanvasEvent[], reset = false) {
  const bySequence = new Map((reset ? [] : previous).map(event => [event.seq, event]));
  incoming.filter(event => event.type === 'graph.changed').forEach(event => bySequence.set(event.seq, event));
  return [...bySequence.values()].sort((a, b) => a.seq - b.seq).slice(-50);
}

export function CollaborationActivity({events, sessionId, onLocate, onUndo}: {
  events: CanvasEvent[]; sessionId?: string;
  onLocate: (document: string, node?: string) => void;
  onUndo: (document: string, transaction: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false), [expanded, setExpanded] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, ChangePreview[]>>({});
  const [next, setNext] = useState<Record<string, number>>({}), [totals, setTotals] = useState<Record<string, number>>({});
  const [error, setError] = useState(''), [pending, setPending] = useState(false);
  async function read(event: CanvasEvent, append = false) {
    const transaction = event.transaction_id;
    if (!sessionId || !transaction || pending) return;
    setPending(true); setError('');
    try {
      const result = await api.agent<{changes: ChangePreview[]; total: number; next_offset: number}>(
        `/sessions/${sessionId}/transactions/${encodeURIComponent(transaction)}?offset=${append ? next[transaction] || 0 : 0}&limit=20`);
      setDetails(previous => ({...previous, [transaction]: [...(append ? previous[transaction] || [] : []), ...result.changes]}));
      setNext(previous => ({...previous, [transaction]: result.next_offset}));
      setTotals(previous => ({...previous, [transaction]: result.total}));
      setExpanded(transaction);
    } catch (failure) {setError((failure as Error).message);} finally {setPending(false);}
  }
  const last = events.at(-1);
  return <div className="collaboration-activity" onPointerDown={event => event.stopPropagation()}>
    <button className="subtle-button collaboration-toggle" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <ClockCounterClockwise size={16}/>{t('协作记录')}
      {last && <span className="collaboration-actor">{last.actor === 'user' ? t('你') : last.actor.replace(/^agent:/, '')}</span>}
    </button>
    {open && <section className="collaboration-popover" aria-label={t('协作记录')}>
      <header><strong>{t('协作记录')}</strong><button className="icon-button" aria-label={t('关闭')} onClick={() => setOpen(false)}><X size={16}/></button></header>
      {!events.length && <p className="collaboration-empty">{t('暂无修改')}</p>}
      <div className="collaboration-list">{[...events].reverse().map(event => {
        const id = event.transaction_id || String(event.seq), target = event.affected?.[0];
        const rows = details[id] || event.changes || [];
        return <article key={event.seq}>
          <div className="collaboration-entry"><strong>{event.actor === 'user' ? t('你') : event.actor.replace(/^agent:/, '')}</strong>
            <time dateTime={event.time}>{new Date(event.time).toLocaleTimeString()}</time></div>
          <button className="collaboration-summary" onClick={() => {if (target) onLocate(target.document_id, target.nodes[0]);}}>
            {event.label === 'Undo' ? t('撤销') : event.label === 'Redo' ? t('重做') : t('已修改 {count} 项', {count: event.change_count || 0})}
          </button>
          <div className="collaboration-entry-actions">
            <button className="text-button" disabled={pending || !event.transaction_id} onClick={() => expanded === id ? setExpanded(null) : void read(event)}>{t('查看差异')}</button>
            {target && event.transaction_id && event.actor !== 'user' && !['Undo', 'Redo'].includes(event.label || '') &&
              <button className="text-button" disabled={pending} onClick={() => {setPending(true); setError(''); void onUndo(target.document_id, event.transaction_id!)
                .catch(failure => setError((failure as Error).message)).finally(() => setPending(false));}}><ArrowCounterClockwise size={13}/>{t('撤销这次修改')}</button>}
          </div>
          {expanded === id && <div className="collaboration-diff">{rows.map((change, index) => <div key={index}>
            <button className="collaboration-path" onClick={() => onLocate(change.document_id, change.path[0] === 'nodes' ? change.path[1] : undefined)}>{change.path.join(' / ')}</button>
            {change.before_exists && <pre className="diff-removed">− {change.before}{change.before_truncated ? ' …' : ''}</pre>}
            {change.after_exists && <pre className="diff-added">+ {change.after}{change.after_truncated ? ' …' : ''}</pre>}
            {(change.before_truncated || change.after_truncated) && <span>{t('长内容已截断，请打开节点查看完整值')}</span>}
          </div>)}{next[id] < totals[id] && <button className="text-button" disabled={pending} onClick={() => void read(event, true)}>{t('更多差异')}</button>}</div>}
        </article>;
      })}</div>
      {error && <p role="alert" className="field-error">{error}</p>}
    </section>}
  </div>;
}
