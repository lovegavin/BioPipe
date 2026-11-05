import {useEffect, useState} from 'react';
import {Desktop, Moon, Sun} from '@phosphor-icons/react';

type Preference = 'system' | 'light' | 'dark';
const KEY = 'biopipe-studio-theme-v1';
const choices = [{value:'light', label:'浅色', Icon:Sun}, {value:'dark', label:'深色', Icon:Moon}, {value:'system', label:'跟随系统', Icon:Desktop}] as const;
function stored(): Preference {
  try {const value = localStorage.getItem(KEY); return value === 'light' || value === 'dark' ? value : 'system';} catch {return 'system';}
}
// Mounted in App, so system-theme changes still apply while Settings is closed.
export function useAppearance() {
  const [preference, setPreference] = useState(stored);
  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      document.documentElement.dataset.theme = preference === 'system' ? system.matches ? 'dark' : 'light' : preference;
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', getComputedStyle(document.documentElement).getPropertyValue('--panel').trim());
    };
    apply(); system.addEventListener('change', apply); return () => system.removeEventListener('change', apply);
  }, [preference]);
  useEffect(() => {
    const update = (e: StorageEvent) => {if (e.key === KEY || e.key === null) setPreference(stored());};
    window.addEventListener('storage', update); return () => window.removeEventListener('storage', update);
  }, []);
  return {preference, onChange: (value: Preference) => {setPreference(value); try {localStorage.setItem(KEY, value);} catch { /* Session theme still works. */ }}};
}
export function AppearanceSettings({preference, onChange}: ReturnType<typeof useAppearance>) {
  return <fieldset className="appearance-settings"><legend>主题</legend><div>{choices.map(({value, label, Icon}) => <label key={value}>
    <input type="radio" name="appearance" value={value} checked={preference === value} onChange={() => onChange(value)}/>
    <span className={`theme-swatch theme-${value}`} aria-hidden="true"><i/><i/><i/></span><span><Icon size={16}/>{label}</span>
  </label>)}</div></fieldset>;
}
