import {t} from './i18n';
import {useEffect, useState} from 'react';
import {Desktop, Moon, Sun} from '@phosphor-icons/react';
import {api} from './api';
import {setPreferences, usePreferences, type ThemePreference} from './preferences';

const choices = [{value:'light', label:'浅色', Icon:Sun}, {value:'dark', label:'深色', Icon:Moon}, {value:'system', label:'跟随系统', Icon:Desktop}] as const;
// Mounted in App, so system-theme changes still apply while Settings is closed.
export function useAppearance() {
  const {theme: preference} = usePreferences();
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => {
      document.documentElement.dataset.theme = preference === 'system' ? system.matches ? 'dark' : 'light' : preference;
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', getComputedStyle(document.documentElement).getPropertyValue('--panel').trim());
    };
    apply(); system.addEventListener('change', apply); return () => system.removeEventListener('change', apply);
  }, [preference]);
  async function onChange(value: ThemePreference) {
    setPending(true); setError('');
    try {setPreferences(await api.savePreferences({theme: value}));}
    catch (error) {setError((error as Error).message);}
    finally {setPending(false);}
  }
  return {preference, pending, error, onChange};
}
export function AppearanceSettings({preference, onChange, pending, error}: {
  preference: ThemePreference; onChange: (value: ThemePreference) => void; pending?: boolean; error?: string;
}) {
  return <fieldset className="appearance-settings"><legend>{t("主题")}</legend><div>{choices.map(({value, label, Icon}) => <label key={value}>
    <input type="radio" name="appearance" value={value} disabled={pending} checked={preference === value} onChange={() => onChange(value)}/>
    <span className={`theme-swatch theme-${value}`} aria-hidden="true"><i/><i/><i/></span><span><Icon size={16}/>{t(label)}</span>
  </label>)}</div>{error && <p className="modal-error" role="alert">{error}</p>}</fieldset>;
}
