import {useEffect, useRef, useState, type ComponentProps} from 'react';
import {HardDrives, Monitor, Palette, X} from '@phosphor-icons/react';
import {RemotePanel} from './RemotePanel';
import {ViewerSettings} from './ViewerSettings';
import {AppearanceSettings} from './AppearanceSettings';
import './settings.css';

export type SettingsSection = 'servers' | 'viewers' | 'appearance';
export function SettingsPage({initial, onClose, appearance, ...remote}: Omit<ComponentProps<typeof RemotePanel>, 'embedded' | 'onBusyChange'> & {
  initial: SettingsSection; appearance: ComponentProps<typeof AppearanceSettings>;
}) {
  const [section, setSection] = useState(initial);
  const [serverBusy, setServerBusy] = useState(false), [viewerBusy, setViewerBusy] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const content = useRef<HTMLElement>(null);
  const busy = serverBusy || viewerBusy;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    element?.showModal();
    return () => {element?.close(); previous?.focus();};
  }, []);
  const sections = [{id:'servers', name:'服务器', Icon:HardDrives}, {id:'viewers', name:'输出与查看器', Icon:Monitor}, {id:'appearance', name:'外观', Icon:Palette}] as const;
  return <dialog className="settings-page" ref={dialog} role="dialog" aria-modal="true" aria-labelledby="settings-title"
    onCancel={e => {e.preventDefault(); if (!busy) onClose();}}
    onKeyDown={e => e.stopPropagation()}>
    <header className="settings-header"><h2 id="settings-title">设置</h2><button className="icon-button" aria-label="关闭设置" disabled={busy} onClick={onClose}><X size={19}/></button></header>
    <div className="settings-layout">
      <nav className="settings-navigation" aria-label="设置分类">{sections.map(({id, name, Icon}) => <button key={id} aria-current={section === id ? 'page' : undefined} onClick={() => {setSection(id); content.current?.scrollTo(0, 0);}}><Icon size={18}/>{name}</button>)}</nav>
      <main className="settings-content" ref={content}>
        <div hidden={section !== 'servers'}><div className="settings-page-heading"><h3>服务器</h3></div><RemotePanel {...remote} embedded onClose={onClose} onBusyChange={setServerBusy}/></div>
        <div hidden={section !== 'viewers'}><div className="settings-page-heading"><h3>输出与查看器</h3></div><ViewerSettings onBusyChange={setViewerBusy}/></div>
        <div hidden={section !== 'appearance'}><div className="settings-page-heading"><h3>外观</h3></div><AppearanceSettings {...appearance}/></div>
      </main>
    </div>
  </dialog>;
}
