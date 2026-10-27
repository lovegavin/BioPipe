import {useEffect, useRef, useState} from 'react';
import {ArrowLeft, ArrowRight, CircleNotch, File, Folder, Plus, HardDrives as Server, X} from '@phosphor-icons/react';
import {api, ApiError} from './api';
import type {DataSource, RemoteListing, RemoteProfile, RemoteStatus} from './types';
import './remote.css';

const empty: RemoteProfile = {name: '', host: '', port: 22, username: '', auth: 'password', key_path: '',
  python: 'python3', app_dir: '', workspace: '', mode: 'exec', menu_choice: ''};

export function remoteId(graph: {runtime?: Record<string, unknown>}): string {
  const value = graph.runtime?.execution as {kind?: string; profile_id?: string} | undefined;
  return value?.kind === 'ssh' ? value.profile_id || '' : '';
}

export function RemotePanel({servers, active, onUpdate, onSelect, onClose}: {
  servers: RemoteStatus[]; active: string; onUpdate: () => Promise<void>; onSelect: (id: string) => void; onClose: () => void;
}) {
  const [profile, setProfile] = useState<RemoteProfile>(() => servers.find(s => s.profile.id === active)?.profile || servers[0]?.profile || {...empty});
  const [password, setPassword] = useState(''), [passphrase, setPassphrase] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [trust, setTrust] = useState<{id: string; fingerprint: string; changed: boolean} | null>(null);
  const selected = servers.find(s => s.profile.id === profile.id);
  useEffect(() => {const key = (e: KeyboardEvent) => {if(e.key === 'Escape' && !busy) onClose();};
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);}, [busy, onClose]);
  function edit(patch: Partial<RemoteProfile>) {setTrust(null); setProfile({...profile, ...patch});}
  async function connect(trusted?: typeof trust) {
    setBusy(true); setError('');
    let saved = profile;
    try {
      saved = trusted ? profile : await api.saveRemote(profile);
      setProfile(saved);
      if (trusted) await api.trustRemote(trusted.id, trusted.fingerprint);
      await api.connectRemote(saved.id!, {password, passphrase});
      setPassword(''); setPassphrase(''); setTrust(null);
      await onUpdate(); onSelect(saved.id!);
    } catch (e) {
      const issue = e as ApiError;
      if (issue.code === 'host_key_required' && issue.details?.fingerprint) {
        if (saved.id) setTrust({id: saved.id, fingerprint: issue.details.fingerprint, changed: !!issue.details.changed});
      } else {setTrust(null); setError(issue.message);}
      await onUpdate();
    } finally {setBusy(false);}
  }
  const field = (label: string, key: 'name' | 'host' | 'username' | 'python' | 'app_dir' | 'workspace' | 'key_path' | 'menu_choice', placeholder = '') =>
    <label className="field"><span>{label}</span><input value={profile[key]} disabled={busy} placeholder={placeholder}
      onChange={e => edit({[key]: e.target.value})} autoComplete="off" required={key !== 'menu_choice' && key !== 'key_path'}/></label>;
  return <div className="agent-overlay" onMouseDown={e => {if(e.target === e.currentTarget && !busy) onClose();}}>
    <section className="remote-panel" role="dialog" aria-modal="true" aria-label="服务器连接">
      <header><h2><Server size={22}/>服务器</h2><button className="icon-button" disabled={busy} onClick={onClose} aria-label="关闭服务器面板"><X size={18}/></button></header>
      <div className="remote-layout"><nav aria-label="已保存的服务器">
        {servers.map(server => <button key={server.profile.id} className={server.profile.id === profile.id ? 'active' : ''} disabled={busy}
          onClick={() => {setProfile(server.profile); setPassword(''); setPassphrase(''); setTrust(null); setError('');}}>
          <Server size={17}/><span><strong>{server.profile.name}</strong><small>{server.connected ? '已连接' : '未连接'}</small></span></button>)}
        <button disabled={busy} onClick={() => {setProfile({...empty}); setTrust(null); setError(''); setPassword(''); setPassphrase('');}}><Plus size={17}/>添加服务器</button>
      </nav><form onSubmit={e => {e.preventDefault(); void connect();}}>
        <div className="remote-fields">
          {field('名称', 'name', '计算服务器')}{field('主机', 'host', 'server.example.org')}
          {field('用户名', 'username')}<label className="field"><span>端口</span><input type="number" min={1} max={65535} required disabled={busy} value={profile.port} onChange={e => edit({port: Number(e.target.value)})}/></label>
          {field('BioPipe 目录', 'app_dir', '/opt/biopipe')}{field('运行目录', 'workspace', '/srv/biopipe-work')}
          {field('Python', 'python', 'python3')}
          <label className="field"><span>认证方式</span><select disabled={busy} value={profile.auth} onChange={e => edit({auth: e.target.value as RemoteProfile['auth']})}>
            <option value="password">密码</option><option value="key">私钥文件</option><option value="agent">SSH Agent</option></select></label>
          {profile.auth === 'password' && <label className="field wide"><span>密码 · 仅本次会话</span><input autoComplete="new-password" type="password" disabled={busy} value={password} onChange={e => setPassword(e.target.value)}/></label>}
          {profile.auth === 'key' && <>{field('本机私钥路径', 'key_path')}<label className="field"><span>私钥口令 · 可选</span><input autoComplete="new-password" type="password" disabled={busy} value={passphrase} onChange={e => setPassphrase(e.target.value)}/></label></>}
        </div>
        <details className="advanced"><summary>SSH 网关</summary><div className="remote-fields">
          <label className="field"><span>登录方式</span><select disabled={busy} value={profile.mode} onChange={e => edit({mode: e.target.value as RemoteProfile['mode']})}><option value="exec">普通 SSH</option><option value="shell">交互式网关</option></select></label>
          {profile.mode === 'shell' && field('实例编号', 'menu_choice', '0')}
        </div></details>
        {trust && <div className="remote-trust" role="alert"><strong>{trust.changed ? '服务器指纹已变化' : '确认服务器指纹'}</strong><code>{trust.fingerprint}</code>
          <button type="button" className="primary-button" disabled={busy} onClick={() => void connect(trust)}>信任并连接</button></div>}
        {error && <p role="alert" className="field-error">{error}</p>}
        {selected?.connected && !error && <div className="remote-connected"><span className="status-dot complete"/>{selected.info?.system} · {selected.info?.version}<code>{selected.info?.python}</code></div>}
        <footer>
          {profile.id && <button type="button" className="subtle-button" disabled={busy} onClick={() => {void api.disconnectRemote(profile.id!).then(onUpdate).catch(e => setError(e.message));}}>断开</button>}
          {profile.id && <button type="button" className="subtle-button" disabled={busy} onClick={() => {void api.removeRemote(profile.id!).then(async () => {setProfile({...empty}); setTrust(null); await onUpdate();}).catch(e => setError(e.message));}}>移除</button>}
          <button className="primary-button" type="submit" disabled={busy || !!trust}>{busy ? <><CircleNotch className="spin" size={16}/>连接中</> : '连接服务器'}</button>
        </footer>
      </form></div>
    </section>
  </div>;
}

export function RemoteFilePicker({profileId, initial, source, onSelect, onClose}: {profileId: string; initial: string; source?: boolean;
  onSelect: (path: string, source?: DataSource) => void; onClose: () => void}) {
  const [path, setPath] = useState(() => initial.includes('/') ? initial.slice(0, initial.lastIndexOf('/')) || '/' : '.');
  const [listing, setListing] = useState<RemoteListing | null>(null), [selected, setSelected] = useState('');
  const [hidden, setHidden] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const request = useRef(0);
  async function browse(value: string, offset = 0) {
    const id = ++request.current; setBusy(true); setError('');
    try {const result = await api.browseRemote(profileId, value, offset, hidden);
      if (id !== request.current) return;
      setListing(prior => offset && prior ? {...result, entries: [...prior.entries, ...result.entries]} : result);
      setPath(result.path); if (!offset) setSelected('');
    } catch(e) {if(id === request.current) setError((e as Error).message);}
    finally {if(id === request.current) setBusy(false);}
  }
  useEffect(() => {void browse(path);}, [hidden]);
  useEffect(() => {const key = (e: KeyboardEvent) => {if(e.key === 'Escape') onClose();}; window.addEventListener('keydown', key);
    return () => {request.current++; window.removeEventListener('keydown', key);};}, []);
  async function choose(value: string) {
    if (!value) return; setBusy(true); setError('');
    try {const result = source ? await api.sourceRemote(profileId, value) : undefined; onSelect(value, result?.source); onClose();}
    catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <div className="agent-overlay"><section className="remote-files" role="dialog" aria-modal="true" aria-label="选择服务器文件">
    <header><h2><Folder size={22}/>服务器文件</h2><button className="icon-button" aria-label="关闭文件选择" onClick={onClose}><X size={18}/></button></header>
    <form className="remote-location" onSubmit={e => {e.preventDefault(); void browse(path);}}>
      <button type="button" className="icon-button" aria-label="上级目录" disabled={busy || !listing || listing.path === listing.parent} onClick={() => void browse(listing!.parent)}><ArrowLeft size={17}/></button>
      <input aria-label="服务器目录" value={path} onChange={e => setPath(e.target.value)}/><button className="icon-button" aria-label="打开目录" disabled={busy}><ArrowRight size={17}/></button>
    </form>
    <div className="remote-file-list" role="listbox" aria-label="服务器文件列表">
      {listing?.entries.map(entry => <button key={entry.path} role="option" aria-selected={selected === entry.path} disabled={busy}
        className={selected === entry.path ? 'selected' : ''} onClick={() => entry.directory ? void browse(entry.path) : setSelected(entry.path)} onDoubleClick={() => {if(!entry.directory) void choose(entry.path);}}>
        {entry.directory ? <Folder size={19}/> : <File size={19}/>}<span>{entry.name}</span><small>{entry.directory ? '' : new Intl.NumberFormat().format(entry.bytes)+' B'}</small></button>)}
      {!busy && listing?.entries.length === 0 && <p className="results-empty">此目录为空</p>}
      {busy && <div className="results-empty"><CircleNotch size={24} className="spin"/></div>}
      {listing?.next_offset != null && <button disabled={busy} onClick={() => void browse(listing.path, listing.next_offset!)}>加载更多</button>}
    </div>
    {error && <p className="field-error" role="alert">{error}</p>}
    <footer><label><input type="checkbox" checked={hidden} onChange={e => setHidden(e.target.checked)}/>显示隐藏文件</label><button className="primary-button" disabled={busy || !selected} onClick={() => void choose(selected)}>选择文件</button></footer>
  </section></div>;
}
