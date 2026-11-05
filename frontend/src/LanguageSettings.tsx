import {Check} from '@phosphor-icons/react';
import {useState} from 'react';
import {t, useLanguagePreference, useLocale, type LanguagePreference} from './i18n';
import {setPreferences} from './preferences';
import {api} from './api';

export function LanguageSettings() {
  const preference = useLanguagePreference();
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  useLocale();
  async function change(value: LanguagePreference) {
    setPending(true); setError('');
    try {setPreferences(await api.savePreferences({language: value}));}
    catch (error) {setError((error as Error).message);}
    finally {setPending(false);}
  }
  const choices = [{value: 'system', label: t('跟随系统')}, {value: 'zh-CN', label: t("简体中文")}, {value: 'en', label: 'English'}] as const;
  return <fieldset className="language-settings"><legend>{t('界面语言')}</legend>
    {choices.map(({value, label}) => <label key={value}>
      <input type="radio" name="language" value={value} disabled={pending} checked={preference === value} onChange={() => void change(value)}/>
      <span>{label}</span>{preference === value && <Check size={18} aria-hidden="true"/>}
    </label>)}
    <p className="settings-note">{t('算子翻译缺失时显示原始语言。')}</p>
    {error && <p className="modal-error" role="alert">{error}</p>}
  </fieldset>;
}
