import {t} from './i18n';
import {useEffect, useRef, useState} from 'react';
import {ArrowLeft, ArrowRight, CircleNotch, File, Folder, Plus, HardDrives as Server, X} from '@phosphor-icons/react';
import {api, ApiError} from './api';
import type {DataSource, RemoteListing, RemoteProfile, RemoteStatus} from './types';
import './remote.css';

const empty: RemoteProfile = {name: '', host: '', port: 22, username: '', auth: 'password', key_path: '',
  python: 'python3', app_dir: '', workspace: '', mode: 'exec', menu_choice: '', environment: 'managed', managed_root: ''};
type ConnectionAction = 'connect' | 'install';

export function remoteId(graph: {runtime?: Record<string, unknown>}): string {
  const value = graph.runtime?.execution as {kind?: string; profile_id?: string} | undefined;
  return value?.kind === 'ssh' ? value.profile_id || '' : '';
}

export function RemotePanel({servers, active, onUpdate, onSelect, onClose, embedded = false, onBusyChange}: {
  servers: RemoteStatus[]; active: string; onUpdate: () => Promise<void>; onSelect: (id: string) => void; onClose: () => void;
  embedded?: boolean; onBusyChange?: (busy: boolean) => void;
}) {
  const [profile, setProfile] = useState<RemoteProfile>(() => servers.find(s => s.profile.id === active)?.profile || servers[0]?.profile || {...empty});
  const [password, setPassword] = useState(''), [passphrase, setPassphrase] = useState('');
  const [busy, setBusy] = useState<ConnectionAction | 'refresh' | null>(null), [error, setError] = useState('');
  const [maintenance, setMaintenance] = useState(false);
  const [setup, setSetup] = useState<string[]>([]);
  useEffect(() => {onBusyChange?.(!!busy);}, [busy, onBusyChange]);
  useEffect(() => {
    if (busy !== 'install' || !profile.id) return;
    let alive = true;
    const refresh = () => {void api.remoteSetup(profile.id!).then(value => {if (alive) setSetup(value.lines);}).catch(() => {});};
    refresh(); const timer = window.setInterval(refresh, 1500);
    return () => {alive = false; window.clearInterval(timer);};
  }, [busy, profile.id]);
  const [trust, setTrust] = useState<{id: string; fingerprint: string; changed: boolean; action: ConnectionAction} | null>(null);
  const selected = servers.find(s => s.profile.id === profile.id);
  const info = selected?.info;
  useEffect(() => {if (embedded) return; const key = (e: KeyboardEvent) => {if(e.key === 'Escape' && !busy) onClose();};
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);}, [busy, onClose, embedded]);
  function edit(patch: Partial<RemoteProfile>) {setTrust(null); setError(''); setProfile({...profile, ...patch});}
  function showError(issue: ApiError) {
    const message = issue.message?.trim();
    const guidance = ['操作未完成，请重试。', t('操作未完成，请重试。')].includes(message) ? '' : message;
    if (issue.code === 'server_not_installed') {
      setMaintenance(true);
      setError(profile.environment === 'managed' ? t("未找到 Operon 服务端，请先安装服务端。") : t("未找到 Operon 服务端，请检查 Operon 目录与 Python 路径。"));
    } else if (['server_incompatible', 'handshake_incompatible', 'capability_missing'].includes(issue.code || '')) {
      setMaintenance(true);
      setError(guidance || (profile.environment === 'managed' ? t("服务端不兼容，请安装 / 升级服务端后重试。") : t("服务端不兼容，请升级指定环境中的 Operon 后重试。")));
    } else if (issue.code === 'handshake_required') {
      setMaintenance(true);
      setError(guidance || t("此服务端需要一次性升级后重新连接。"));
    } else setError(issue.message);
  }
  async function connect(action: ConnectionAction, trusted?: typeof trust) {
    if (busy) return;
    setBusy(action); setError(''); setSetup([]);
    let saved = profile;
    try {
      saved = trusted ? profile : await api.saveRemote(profile);
      setProfile(saved);
      if (trusted) await api.trustRemote(trusted.id, trusted.fingerprint);
      await (action === 'install' ? api.installRemote : api.connectRemote)(saved.id!, {password, passphrase});
      setPassword(''); setPassphrase(''); setTrust(null);
      await onUpdate(); onSelect(saved.id!);
    } catch (e) {
      const issue = e as ApiError;
      if (issue.code === 'host_key_required' && issue.details?.fingerprint) {
        if (saved.id) setTrust({id: saved.id, fingerprint: issue.details.fingerprint, changed: !!issue.details.changed, action});
      } else {setTrust(null); showError(issue);}
      await onUpdate();
    } finally {setBusy(null);}
  }
  async function refresh() {
    if (busy || trust || !selected?.connected || !profile.id) return;
    setBusy('refresh'); setError(''); setSetup([]);
    try {await api.refreshRemote(profile.id); await onUpdate();}
    catch(e) {showError(e as ApiError); await onUpdate();}
    finally {setBusy(null);}
  }
  const field = (label: string, key: 'name' | 'host' | 'username' | 'python' | 'app_dir' | 'workspace' | 'key_path' | 'menu_choice' | 'managed_root', placeholder = '') =>
    <label className="field"><span>{label}</span><input value={profile[key] || ''} disabled={!!busy} placeholder={placeholder}
      onChange={e => edit({[key]: e.target.value})} autoComplete="off" required={['name', 'host', 'username'].includes(key) || (profile.environment !== 'managed' && ['app_dir', 'workspace', 'python'].includes(key))}/></label>;
  const panel = <section className={`remote-panel${embedded ? ' remote-embedded' : ''}`} role={embedded ? undefined : 'dialog'} aria-modal={embedded ? undefined : true} aria-label={t("服务器连接")}>
      {!embedded && <header><h2><Server size={22}/>{t("服务器")}</h2><button className="icon-button" disabled={!!busy} onClick={onClose} aria-label={t("关闭服务器面板")}><X size={18}/></button></header>}
      <div className="remote-layout"><nav aria-label={t("已保存的服务器")}>
        {servers.map(server => <button key={server.profile.id} className={server.profile.id === profile.id ? 'active' : ''} disabled={!!busy}
          onClick={() => {setProfile(server.profile); setPassword(''); setPassphrase(''); setTrust(null); setError(''); setSetup([]); setMaintenance(false);}}>
          <Server size={17}/><span><strong>{server.profile.name}</strong><small>{server.connected ? t("已连接") : t("未连接")}</small></span></button>)}
        <button disabled={!!busy} onClick={() => {setProfile({...empty}); setTrust(null); setError(''); setPassword(''); setPassphrase(''); setSetup([]); setMaintenance(false);}}><Plus size={17}/>{t("添加服务器")}</button>
      </nav><form onSubmit={e => {e.preventDefault(); if (!trust) void connect('connect');}}>
        <div className="remote-fields">
          {field(t("名称"), 'name', t("计算服务器"))}{field(t("主机"), 'host', 'server.example.org')}
          {field(t("用户名"), 'username')}<label className="field"><span>{t("端口")}</span><input type="number" min={1} max={65535} required disabled={!!busy} value={profile.port} onChange={e => edit({port: Number(e.target.value)})}/></label>
          <label className="field"><span>{t("服务器环境")}</span><select disabled={!!busy} value={profile.environment || 'existing'} onChange={e => edit({environment: e.target.value as RemoteProfile['environment']})}>
            <option value="managed">{t("已安装的 Operon 服务端")}</option><option value="existing">{t("手动指定环境")}</option></select></label>
          {profile.environment === 'managed' ? field(t("安装目录 · 可选"), 'managed_root', t("服务器用户目录下的标准位置")) : <>{field(t("Operon 目录"), 'app_dir', '/opt/operon')}{field('Python', 'python', 'python3')}</>}
          {field(t("运行目录"), 'workspace', profile.environment === 'managed' ? t("安装目录下自动创建") : '/srv/operon-work')}
          <label className="field"><span>{t("认证方式")}</span><select disabled={!!busy} value={profile.auth} onChange={e => edit({auth: e.target.value as RemoteProfile['auth']})}>
            <option value="password">{t("密码")}</option><option value="key">{t("私钥文件")}</option><option value="agent">SSH Agent</option></select></label>
          {profile.auth === 'password' && <label className="field wide"><span>{t("密码 · 仅本次会话")}</span><input autoComplete="new-password" type="password" disabled={!!busy} value={password} onChange={e => setPassword(e.target.value)}/></label>}
          {profile.auth === 'key' && <>{field(t("本机私钥路径"), 'key_path')}<label className="field"><span>{t("私钥口令 · 可选")}</span><input autoComplete="new-password" type="password" disabled={!!busy} value={passphrase} onChange={e => setPassphrase(e.target.value)}/></label></>}
        </div>
        <details className="advanced"><summary>{t("SSH 网关")}</summary><div className="remote-fields">
          <label className="field"><span>{t("登录方式")}</span><select disabled={!!busy} value={profile.mode} onChange={e => edit({mode: e.target.value as RemoteProfile['mode']})}><option value="exec">{t("普通 SSH")}</option><option value="shell">{t("交互式网关")}</option></select></label>
          {profile.mode === 'shell' && field(t("实例编号"), 'menu_choice', '0')}
        </div></details>
        {profile.environment === 'managed' && <details className="remote-maintenance" open={maintenance} onToggle={e => setMaintenance(e.currentTarget.open)}>
          <summary>{t("服务端维护")}</summary>
          <button type="button" className="subtle-button" disabled={!!busy || !!trust} onClick={e => {if (e.currentTarget.form?.reportValidity()) void connect('install');}}>
            {busy === 'install' ? <><CircleNotch className="spin" size={16}/>{t("安装中")}</> : t("安装 / 升级服务端")}</button>
        </details>}
        {trust && <div className="remote-trust" role="alert"><strong>{trust.changed ? t("服务器指纹已变化") : t("确认服务器指纹")}</strong><code>{trust.fingerprint}</code>
          <button type="button" className="primary-button" disabled={!!busy} onClick={() => void connect(trust.action, trust)}>{trust.action === 'install' ? t("信任并安装 / 升级") : t("信任并连接")}</button></div>}
        {error && <p role="alert" className="field-error">{error}</p>}
        {!!setup.length && <details className="remote-setup" open={busy === 'install'}><summary>{busy === 'install' ? setup[setup.length - 1] : t("服务端安装记录")}</summary><pre role="log" aria-live="polite">{setup.join('\n')}</pre></details>}
        {selected?.connected && <div className="remote-connected" aria-label={t("服务端状态")}>
          <div className="remote-status-heading"><span className="status-dot complete"/><strong title={info?.python}>{info ? `Operon ${info.version}` : t("已连接")}</strong><span>{info?.system}</span>
            <button type="button" className="subtle-button" disabled={!!busy || !!trust} onClick={() => void refresh()}>{busy === 'refresh' ? <><CircleNotch className="spin" size={14}/>{t("刷新中")}</> : t("刷新算子与依赖")}</button></div>
          {info && <div className="remote-status-counts"><span>{t("算子")} {info.catalog.operators.length}</span>
            {info.dependencies && <span>{t("依赖")} {info.dependencies.entries.filter(entry => entry.status === 'passed').length}/{info.dependencies.entries.length} {t("已通过")}{info.dependencies.running ? t(" · 检查中") : ''}</span>}
            {!!Object.keys(info.tools || {}).length && <span>{t("工具")} {Object.values(info.tools).filter(Boolean).length}/{Object.keys(info.tools).length} {t("可用")}</span>}
          </div>}
        </div>}
        <footer>
          {(busy === 'connect' || busy === 'install') && profile.id && <button type="button" className="subtle-button" onClick={() => {void api.disconnectRemote(profile.id!).catch(e => setError(e.message));}}>{busy === 'install' ? t("取消安装") : t("取消连接")}</button>}
          {profile.id && <button type="button" className="subtle-button" disabled={!!busy} onClick={() => {void api.disconnectRemote(profile.id!).then(onUpdate).catch(e => setError(e.message));}}>{t("断开")}</button>}
          {profile.id && <button type="button" className="subtle-button" disabled={!!busy} onClick={() => {void api.removeRemote(profile.id!).then(async () => {setProfile({...empty}); setTrust(null); setPassword(''); setPassphrase(''); setSetup([]); setError(''); setMaintenance(false); await onUpdate();}).catch(e => setError(e.message));}}>{t("移除")}</button>}
          <button className="primary-button" type="submit" disabled={!!busy || !!trust}>{busy === 'connect' ? <><CircleNotch className="spin" size={16}/>{t("连接中")}</> : t("连接服务器")}</button>
        </footer>
      </form></div>
    </section>;
  return embedded ? panel : <div className="agent-overlay" onMouseDown={e => {if(e.target === e.currentTarget && !busy) onClose();}}>{panel}</div>;
}

export function RemoteFilePicker({profileId, initial, source, reader, onSelect, onClose}: {profileId: string; initial: string; source?: boolean; reader?: string;
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
    try {const result = source ? await api.sourceRemote(profileId, value, reader) : undefined; onSelect(value, result?.source); onClose();}
    catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <div className="agent-overlay"><section className="remote-files" role="dialog" aria-modal="true" aria-label={t("选择服务器文件")}>
    <header><h2><Folder size={22}/>{t("服务器文件")}</h2><button className="icon-button" aria-label={t("关闭文件选择")} onClick={onClose}><X size={18}/></button></header>
    <form className="remote-location" onSubmit={e => {e.preventDefault(); void browse(path);}}>
      <button type="button" className="icon-button" aria-label={t("上级目录")} disabled={busy || !listing || listing.path === listing.parent} onClick={() => void browse(listing!.parent)}><ArrowLeft size={17}/></button>
      <input aria-label={t("服务器目录")} value={path} onChange={e => setPath(e.target.value)}/><button className="icon-button" aria-label={t("打开目录")} disabled={busy}><ArrowRight size={17}/></button>
    </form>
    <div className="remote-file-list" role="listbox" aria-label={t("服务器文件列表")}>
      {listing?.entries.map(entry => <button key={entry.path} role="option" aria-selected={selected === entry.path} disabled={busy}
        className={selected === entry.path ? 'selected' : ''} onClick={() => entry.directory ? void browse(entry.path) : setSelected(entry.path)} onDoubleClick={() => {if(!entry.directory) void choose(entry.path);}}>
        {entry.directory ? <Folder size={19}/> : <File size={19}/>}<span>{entry.name}</span><small>{entry.directory ? '' : new Intl.NumberFormat().format(entry.bytes)+' B'}</small></button>)}
      {!busy && listing?.entries.length === 0 && <p className="results-empty">{t("此目录为空")}</p>}
      {busy && <div className="results-empty"><CircleNotch size={24} className="spin"/></div>}
      {listing?.next_offset != null && <button disabled={busy} onClick={() => void browse(listing.path, listing.next_offset!)}>{t("加载更多")}</button>}
    </div>
    {error && <p className="field-error" role="alert">{error}</p>}
    <footer><label><input type="checkbox" checked={hidden} onChange={e => setHidden(e.target.checked)}/>{t("显示隐藏文件")}</label><button className="primary-button" disabled={busy || !selected} onClick={() => void choose(selected)}>{t("选择文件")}</button></footer>
  </section></div>;
}
